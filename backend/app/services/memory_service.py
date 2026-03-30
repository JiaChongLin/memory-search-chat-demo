from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from backend.app.db.models import ChatMessage, ChatSession, Project, SessionSummary, utcnow


MessageRole = Literal["user", "assistant", "system"]
ContextScope = Literal[
    "conversation_only",
    "project_only",
    "project_plus_global",
    "global",
]
MAX_RELATED_SUMMARIES = 8


@dataclass
class MemoryMessage:
    role: MessageRole
    content: str


@dataclass
class RelatedSummary:
    session_id: str
    project_id: Optional[int]
    content: str
    source_scope: Literal["project", "global"]


@dataclass
class ResolvedContext:
    recent_messages: list[MemoryMessage]
    context_summary: Optional[str]
    context_scope: ContextScope
    related_summaries: list[RelatedSummary]


class MemoryService:
    """负责会话记忆、摘要和上下文访问边界解析。"""

    def __init__(
        self,
        db: Session,
        short_window: int = 6,
        summary_enabled: bool = True,
        summary_max_chars: int = 600,
    ) -> None:
        self._db = db
        self._short_window = max(2, short_window)
        self._summary_enabled = summary_enabled
        self._summary_max_chars = max(120, summary_max_chars)

    def resolve_context(self, session_id: str) -> ResolvedContext:
        current_session = self._get_readable_session(session_id)
        recent_messages = self.get_recent_messages(session_id) if current_session else []
        current_summary = self.get_summary(session_id) if current_session else None

        if current_session is None:
            return ResolvedContext(
                recent_messages=recent_messages,
                context_summary=current_summary,
                context_scope="conversation_only",
                related_summaries=[],
            )

        context_scope = self._resolve_context_scope(current_session)
        related_summaries: list[RelatedSummary] = []
        if context_scope != "conversation_only":
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

    def get_recent_messages(self, session_id: str) -> list[MemoryMessage]:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(self._short_window)
        )
        messages = list(self._db.scalars(stmt))
        messages.reverse()
        return [self._to_memory_message(message) for message in messages]

    def get_summary(self, session_id: str) -> Optional[str]:
        stmt = select(SessionSummary).where(SessionSummary.session_id == session_id)
        summary = self._db.execute(stmt).scalar_one_or_none()
        return summary.content if summary else None

    def get_accessible_summaries(
        self,
        current_session: ChatSession,
        context_scope: ContextScope,
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
                    self._to_related_summary(candidate, source_scope="project")
                )
                continue

            if context_scope in {"project_plus_global", "global"} and self._can_read_across_boundary(
                current_session,
                candidate,
            ):
                global_items.append(
                    self._to_related_summary(candidate, source_scope="global")
                )

        if context_scope == "project_only":
            return same_project_items[:MAX_RELATED_SUMMARIES]

        return (same_project_items + global_items)[:MAX_RELATED_SUMMARIES]

    def append_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
    ) -> Optional[str]:
        try:
            session = self._get_or_create_session(session_id)
            session.updated_at = utcnow()

            self._db.add_all(
                [
                    ChatMessage(
                        session_id=session_id,
                        role="user",
                        content=user_message,
                    ),
                    ChatMessage(
                        session_id=session_id,
                        role="assistant",
                        content=assistant_message,
                    ),
                ]
            )
            self._db.flush()

            updated_summary = self.get_summary(session_id)
            if self._summary_enabled:
                messages = self._list_messages(session_id)
                updated_summary = self._build_summary(messages)
                self._save_summary(session_id, updated_summary)

            self._db.commit()
            return updated_summary
        except Exception:
            self._db.rollback()
            raise

    def _get_or_create_session(self, session_id: str) -> ChatSession:
        session = self._db.get(ChatSession, session_id)
        if session is None:
            session = ChatSession(id=session_id)
            self._db.add(session)
            self._db.flush()
        return session

    def _get_readable_session(self, session_id: str) -> Optional[ChatSession]:
        session = self._db.get(ChatSession, session_id)
        if session is None or session.status == "deleted":
            return None
        return session

    def _resolve_context_scope(self, current_session: ChatSession) -> ContextScope:
        if current_session.is_private:
            return "conversation_only"

        project = current_session.project
        if project is None or project.status == "deleted":
            return "conversation_only"

        scope_mode = project.scope_mode
        if scope_mode not in {
            "conversation_only",
            "project_only",
            "project_plus_global",
            "global",
        }:
            return "conversation_only"

        return scope_mode

    def _is_summary_candidate(self, candidate: ChatSession) -> bool:
        if candidate.status != "active":
            return False
        if candidate.is_private:
            return False
        if candidate.summary is None or not candidate.summary.content.strip():
            return False
        if candidate.project is not None and candidate.project.status == "deleted":
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
        source_scope: Literal["project", "global"],
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
                source_label = "同项目" if item.source_scope == "project" else "全局可访问"
                lines.append(f"{index}. {source_label}会话 {item.session_id[:8]}：{item.content}")
            parts.append("\n".join(lines))

        combined = "\n\n".join(parts).strip()
        return combined or None

    def _list_messages(self, session_id: str) -> list[MemoryMessage]:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        )
        return [self._to_memory_message(message) for message in self._db.scalars(stmt)]

    def _save_summary(self, session_id: str, summary: Optional[str]) -> None:
        stmt = select(SessionSummary).where(SessionSummary.session_id == session_id)
        summary_record = self._db.execute(stmt).scalar_one_or_none()

        if not summary:
            if summary_record is not None:
                self._db.delete(summary_record)
            return

        if summary_record is None:
            summary_record = SessionSummary(session_id=session_id, content=summary)
            self._db.add(summary_record)
            return

        summary_record.content = summary
        summary_record.updated_at = utcnow()

    def _to_memory_message(self, message: ChatMessage) -> MemoryMessage:
        if message.role not in {"user", "assistant", "system"}:
            role = "system"
        else:
            role = message.role
        return MemoryMessage(role=role, content=message.content)

    def _build_summary(self, messages: list[MemoryMessage]) -> Optional[str]:
        if len(messages) <= self._short_window:
            return None

        older_messages = messages[:-self._short_window]
        condensed_parts: list[str] = []

        for message in older_messages[-6:]:
            speaker = self._speaker_name(message.role)
            cleaned_content = " ".join(message.content.split())
            condensed_parts.append(f"{speaker}: {cleaned_content[:80]}")

        summary = " | ".join(condensed_parts).strip()
        return summary[: self._summary_max_chars] or None

    def _speaker_name(self, role: MessageRole) -> str:
        if role == "user":
            return "用户"
        if role == "assistant":
            return "助手"
        return "系统"
