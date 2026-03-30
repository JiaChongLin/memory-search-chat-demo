from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from backend.app.db.models import ChatSession
from backend.app.domain.constants import (
    PROJECT_ACCESS_OPEN,
    PROJECT_ACCESS_PROJECT_ONLY,
    RELATED_SUMMARY_SOURCE_EXTERNAL,
    RELATED_SUMMARY_SOURCE_PROJECT,
    ProjectAccessMode,
    RelatedSummarySourceScope,
    STATUS_ACTIVE,
    STATUS_ARCHIVED,
)
from backend.app.services.memory_service import MemoryMessage, MemoryService


MAX_RELATED_SUMMARIES = 8


@dataclass
class RelatedSummary:
    session_id: str
    project_id: Optional[int]
    content: str
    source_scope: RelatedSummarySourceScope


@dataclass
class ResolvedContext:
    recent_messages: list[MemoryMessage]
    context_summary: Optional[str]
    context_scope: ProjectAccessMode
    related_summaries: list[RelatedSummary]


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
        current_summary = self._memory_service.get_summary(session_id)

        if current_session is None:
            current_session = ChatSession(id=session_id, status=STATUS_ACTIVE, is_private=False)

        context_scope = self._resolve_context_scope(current_session)
        related_summaries = self.get_accessible_summaries(current_session)

        return ResolvedContext(
            recent_messages=recent_messages,
            context_summary=self._compose_context_summary(
                current_summary=current_summary,
                related_summaries=related_summaries,
            ),
            context_scope=context_scope,
            related_summaries=related_summaries,
        )

    def get_accessible_summaries(self, current_session: ChatSession) -> list[RelatedSummary]:
        stmt = (
            select(ChatSession)
            .options(
                joinedload(ChatSession.project),
                joinedload(ChatSession.summary),
            )
            .where(ChatSession.id != current_session.id)
            .order_by(ChatSession.updated_at.desc(), ChatSession.created_at.desc())
        )
        candidates = list(self._db.scalars(stmt).unique())

        same_project_items: list[RelatedSummary] = []
        external_items: list[RelatedSummary] = []
        can_read_external = self._can_read_external(current_session)

        for candidate in candidates:
            if not self._is_summary_candidate(candidate):
                continue

            if self._is_same_project(current_session, candidate):
                same_project_items.append(
                    self._to_related_summary(candidate, RELATED_SUMMARY_SOURCE_PROJECT)
                )
                continue

            if can_read_external and self._is_externally_visible(candidate):
                external_items.append(
                    self._to_related_summary(candidate, RELATED_SUMMARY_SOURCE_EXTERNAL)
                )

        return (same_project_items + external_items)[:MAX_RELATED_SUMMARIES]

    def _get_current_session(
        self,
        session_id: str,
        *,
        allow_missing: bool,
    ) -> Optional[ChatSession]:
        stmt = (
            select(ChatSession)
            .options(
                joinedload(ChatSession.project),
                joinedload(ChatSession.summary),
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

    def _can_read_external(self, current_session: ChatSession) -> bool:
        return self._resolve_context_scope(current_session) == PROJECT_ACCESS_OPEN

    def _is_summary_candidate(self, candidate: ChatSession) -> bool:
        if candidate.status != STATUS_ACTIVE:
            return False
        if candidate.is_private:
            return False
        if candidate.summary is None or not candidate.summary.content.strip():
            return False
        if candidate.project is not None and candidate.project.status != STATUS_ACTIVE:
            return False
        return True

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

    def _to_related_summary(
        self,
        candidate: ChatSession,
        source_scope: RelatedSummarySourceScope,
    ) -> RelatedSummary:
        return RelatedSummary(
            session_id=candidate.id,
            project_id=candidate.project_id,
            content=candidate.summary.content if candidate.summary else "",
            source_scope=source_scope,
        )

    def _compose_context_summary(
        self,
        current_summary: Optional[str],
        related_summaries: list[RelatedSummary],
    ) -> Optional[str]:
        parts: list[str] = []

        if current_summary:
            parts.append(f"当前会话摘要：\n{current_summary}")

        if related_summaries:
            lines = ["可访问的相关历史摘要："]
            for index, item in enumerate(related_summaries, start=1):
                source_label = (
                    "同项目"
                    if item.source_scope == RELATED_SUMMARY_SOURCE_PROJECT
                    else "外部可访问"
                )
                lines.append(f"{index}. {source_label}会话 {item.session_id[:8]}：{item.content}")
            parts.append("\n".join(lines))

        combined = "\n\n".join(parts).strip()
        return combined or None
