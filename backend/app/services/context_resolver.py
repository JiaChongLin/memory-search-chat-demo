from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from backend.app.db.models import ChatSession
from backend.app.domain.constants import (
    PROJECT_SCOPE_MODES,
    RELATED_SUMMARY_SOURCE_GLOBAL,
    RELATED_SUMMARY_SOURCE_PROJECT,
    RelatedSummarySourceScope,
    ProjectScopeMode,
    SCOPE_MODE_CONVERSATION_ONLY,
    SCOPE_MODE_GLOBAL,
    SCOPE_MODE_PROJECT_ONLY,
    SCOPE_MODE_PROJECT_PLUS_GLOBAL,
    STATUS_ACTIVE,
    STATUS_DELETED,
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
    context_scope: ProjectScopeMode
    related_summaries: list[RelatedSummary]


class ContextResolver:
    """Resolve readable chat context under project and session boundaries."""

    def __init__(self, db: Session, memory_service: MemoryService) -> None:
        self._db = db
        self._memory_service = memory_service

    def resolve_context(self, session_id: str) -> ResolvedContext:
        current_session = self._get_readable_session(session_id)
        recent_messages = self._memory_service.get_recent_messages(session_id) if current_session else []
        current_summary = self._memory_service.get_summary(session_id) if current_session else None

        if current_session is None:
            return ResolvedContext(
                recent_messages=recent_messages,
                context_summary=current_summary,
                context_scope=SCOPE_MODE_CONVERSATION_ONLY,
                related_summaries=[],
            )

        context_scope = self._resolve_context_scope(current_session)
        related_summaries: list[RelatedSummary] = []
        if context_scope != SCOPE_MODE_CONVERSATION_ONLY:
            related_summaries = self.get_accessible_summaries(current_session, context_scope)

        return ResolvedContext(
            recent_messages=recent_messages,
            context_summary=self._compose_context_summary(
                current_summary=current_summary,
                related_summaries=related_summaries,
            ),
            context_scope=context_scope,
            related_summaries=related_summaries,
        )

    def get_accessible_summaries(
        self,
        current_session: ChatSession,
        context_scope: ProjectScopeMode,
    ) -> list[RelatedSummary]:
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
        global_items: list[RelatedSummary] = []

        for candidate in candidates:
            if not self._is_summary_candidate(candidate):
                continue

            if self._is_same_project(current_session, candidate):
                same_project_items.append(
                    self._to_related_summary(candidate, source_scope=RELATED_SUMMARY_SOURCE_PROJECT)
                )
                continue

            if context_scope in {SCOPE_MODE_PROJECT_PLUS_GLOBAL, SCOPE_MODE_GLOBAL} and self._can_read_across_boundary(
                current_session,
                candidate,
            ):
                global_items.append(
                    self._to_related_summary(candidate, source_scope=RELATED_SUMMARY_SOURCE_GLOBAL)
                )

        if context_scope == SCOPE_MODE_PROJECT_ONLY:
            return same_project_items[:MAX_RELATED_SUMMARIES]

        return (same_project_items + global_items)[:MAX_RELATED_SUMMARIES]

    def _get_readable_session(self, session_id: str) -> Optional[ChatSession]:
        stmt = (
            select(ChatSession)
            .options(
                joinedload(ChatSession.project),
                joinedload(ChatSession.summary),
            )
            .where(ChatSession.id == session_id)
        )
        session = self._db.scalars(stmt).unique().one_or_none()
        if session is None or session.status == STATUS_DELETED:
            return None
        return session

    def _resolve_context_scope(self, current_session: ChatSession) -> ProjectScopeMode:
        if current_session.is_private:
            return SCOPE_MODE_CONVERSATION_ONLY

        project = current_session.project
        if project is None or project.status == STATUS_DELETED:
            return SCOPE_MODE_CONVERSATION_ONLY

        if project.scope_mode not in PROJECT_SCOPE_MODES:
            return SCOPE_MODE_CONVERSATION_ONLY

        return project.scope_mode

    def _is_summary_candidate(self, candidate: ChatSession) -> bool:
        if candidate.status != STATUS_ACTIVE:
            return False
        if candidate.is_private:
            return False
        if candidate.summary is None or not candidate.summary.content.strip():
            return False
        if candidate.project is not None and candidate.project.status == STATUS_DELETED:
            return False
        return True

    def _is_same_project(
        self,
        current_session: ChatSession,
        candidate: ChatSession,
    ) -> bool:
        return (
            current_session.project_id is not None
            and candidate.project_id is not None
            and current_session.project_id == candidate.project_id
        )

    def _can_read_across_boundary(
        self,
        current_session: ChatSession,
        candidate: ChatSession,
    ) -> bool:
        current_project = current_session.project
        candidate_project = candidate.project

        if current_project is not None and current_project.is_isolated:
            return False
        if candidate_project is not None and candidate_project.is_isolated:
            return False
        return True

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
                source_label = "同项目" if item.source_scope == RELATED_SUMMARY_SOURCE_PROJECT else "全局可访问"
                lines.append(f"{index}. {source_label}会话 {item.session_id[:8]}：{item.content}")
            parts.append("\n".join(lines))

        combined = "\n\n".join(parts).strip()
        return combined or None
