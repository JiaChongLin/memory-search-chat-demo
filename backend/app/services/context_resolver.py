from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from backend.app.db.models import ChatSession, Project, SessionSummary
from backend.app.domain.constants import (
    PROJECT_ACCESS_OPEN,
    PROJECT_ACCESS_PROJECT_ONLY,
    RELATED_SUMMARY_SOURCE_EXTERNAL,
    RELATED_SUMMARY_SOURCE_PROJECT,
    SESSION_SUMMARY_KIND_SESSION_DIGEST,
    ProjectAccessMode,
    RelatedSummarySourceScope,
    STATUS_ACTIVE,
    STATUS_ARCHIVED,
)
from backend.app.services.memory_service import MemoryMessage, MemoryService


MAX_RELATED_SUMMARIES = 8
DEFAULT_SESSION_TITLE = "未命名会话"


@dataclass
class RelatedSessionDigest:
    session_id: str
    session_title: str
    project_id: Optional[int]
    content: str
    source_scope: RelatedSummarySourceScope


@dataclass
class ResolvedContext:
    recent_messages: list[MemoryMessage]
    working_memory: Optional[str]
    context_scope: ProjectAccessMode
    related_session_digests: list[RelatedSessionDigest]
    stable_facts: list[str]
    project_name: Optional[str] = None
    project_instruction: Optional[str] = None


class ContextResolver:
    """Resolve readable chat context under the current project/session access model."""

    def __init__(self, db: Session, memory_service: MemoryService) -> None:
        self._db = db
        self._memory_service = memory_service

    def resolve_context(
        self,
        session_id: str,
        *,
        allow_missing: bool = True,
    ) -> ResolvedContext:
        current_session = self._get_current_session(session_id, allow_missing=allow_missing)
        recent_messages = self._memory_service.get_recent_messages(session_id)
        current_working_memory = self._memory_service.get_working_memory(session_id)

        if current_session is None:
            current_session = ChatSession(id=session_id, status=STATUS_ACTIVE, is_private=False)

        context_scope = self._resolve_context_scope(current_session)
        related_session_digests = self.get_accessible_session_digests(current_session)
        project_name, project_instruction = self._resolve_project_prompt_context(current_session)
        stable_facts = self._resolve_project_stable_facts(current_session)

        return ResolvedContext(
            recent_messages=recent_messages,
            working_memory=current_working_memory,
            context_scope=context_scope,
            related_session_digests=related_session_digests,
            stable_facts=stable_facts,
            project_name=project_name,
            project_instruction=project_instruction,
        )

    def get_accessible_session_digests(
        self,
        current_session: ChatSession,
    ) -> list[RelatedSessionDigest]:
        stmt = self._build_digest_candidate_query(current_session)
        candidates = list(self._db.scalars(stmt).unique())

        same_project_items: list[RelatedSessionDigest] = []
        external_items: list[RelatedSessionDigest] = []
        can_read_external = self._can_read_external(current_session)

        for candidate in candidates:
            if self._is_same_project(current_session, candidate):
                same_project_items.append(
                    self._to_related_session_digest(
                        candidate,
                        RELATED_SUMMARY_SOURCE_PROJECT,
                    )
                )
                continue

            if can_read_external and self._is_externally_visible(candidate):
                external_items.append(
                    self._to_related_session_digest(
                        candidate,
                        RELATED_SUMMARY_SOURCE_EXTERNAL,
                    )
                )

        return (same_project_items + external_items)[:MAX_RELATED_SUMMARIES]

    def _build_digest_candidate_query(self, current_session: ChatSession):
        return (
            select(ChatSession)
            .join(
                SessionSummary,
                and_(
                    ChatSession.id == SessionSummary.session_id,
                    SessionSummary.kind == SESSION_SUMMARY_KIND_SESSION_DIGEST,
                ),
            )
            .outerjoin(Project, ChatSession.project_id == Project.id)
            .options(
                joinedload(ChatSession.project),
                joinedload(ChatSession.summaries),
            )
            .where(
                ChatSession.id != current_session.id,
                ChatSession.status == STATUS_ACTIVE,
                ChatSession.is_private.is_(False),
                func.length(func.trim(SessionSummary.content)) > 0,
                or_(Project.id.is_(None), Project.status == STATUS_ACTIVE),
            )
            .order_by(ChatSession.updated_at.desc(), ChatSession.created_at.desc())
        )

    def _get_current_session(
        self,
        session_id: str,
        *,
        allow_missing: bool,
    ) -> Optional[ChatSession]:
        stmt = (
            select(ChatSession)
            .options(
                joinedload(ChatSession.project).joinedload(Project.stable_facts),
                joinedload(ChatSession.summaries),
            )
            .where(ChatSession.id == session_id)
        )
        session = self._db.scalars(stmt).unique().one_or_none()
        if session is None:
            if allow_missing:
                return None
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found.",
            )
        if session.status == STATUS_ARCHIVED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Archived sessions cannot continue chatting.",
            )
        if session.status != STATUS_ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found.",
            )
        return session

    def _resolve_context_scope(self, current_session: ChatSession) -> ProjectAccessMode:
        project = current_session.project
        if project is None or project.status != STATUS_ACTIVE:
            return PROJECT_ACCESS_OPEN
        if project.access_mode == PROJECT_ACCESS_PROJECT_ONLY:
            return PROJECT_ACCESS_PROJECT_ONLY
        return PROJECT_ACCESS_OPEN

    def _resolve_project_prompt_context(
        self,
        current_session: ChatSession,
    ) -> tuple[Optional[str], Optional[str]]:
        project = current_session.project
        if project is None or project.status != STATUS_ACTIVE:
            return None, None
        return project.name, project.instruction

    def _resolve_project_stable_facts(self, current_session: ChatSession) -> list[str]:
        project = current_session.project
        if project is None or project.status != STATUS_ACTIVE:
            return []

        active_facts = [
            fact
            for fact in project.stable_facts
            if fact.status == STATUS_ACTIVE and fact.content and fact.content.strip()
        ]
        active_facts.sort(key=lambda item: (item.updated_at, item.id), reverse=True)
        return [fact.content for fact in active_facts]

    def _can_read_external(self, current_session: ChatSession) -> bool:
        return self._resolve_context_scope(current_session) == PROJECT_ACCESS_OPEN

    def _is_same_project(self, current_session: ChatSession, candidate: ChatSession) -> bool:
        return (
            current_session.project_id is not None
            and candidate.project_id is not None
            and current_session.project_id == candidate.project_id
        )

    def _is_externally_visible(self, candidate: ChatSession) -> bool:
        candidate_project = candidate.project
        if candidate_project is None:
            return True
        if candidate_project.status != STATUS_ACTIVE:
            return False
        return candidate_project.access_mode == PROJECT_ACCESS_OPEN

    def _to_related_session_digest(
        self,
        candidate: ChatSession,
        source_scope: RelatedSummarySourceScope,
    ) -> RelatedSessionDigest:
        return RelatedSessionDigest(
            session_id=candidate.id,
            session_title=(candidate.title or DEFAULT_SESSION_TITLE).strip() or DEFAULT_SESSION_TITLE,
            project_id=candidate.project_id,
            content=self._get_summary_content(candidate, SESSION_SUMMARY_KIND_SESSION_DIGEST) or "",
            source_scope=source_scope,
        )

    def _get_summary_content(self, session: ChatSession, kind: str) -> Optional[str]:
        for record in session.summaries:
            if record.kind == kind:
                return record.content
        return None
