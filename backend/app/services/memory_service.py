from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import ChatMessage, ChatSession, SessionSummary, utcnow
from backend.app.domain.constants import (
    SESSION_SUMMARY_KIND_SESSION_DIGEST,
    SESSION_SUMMARY_KIND_WORKING_MEMORY,
    SessionSummaryKind,
)


MessageRole = Literal["user", "assistant", "system"]


@dataclass
class MemoryMessage:
    role: MessageRole
    content: str


@dataclass
class MemorySnapshot:
    working_memory: Optional[str]
    session_digest: Optional[str]
    summary_updated_at: Optional[datetime] = None


class MemoryService:
    """Persist chat messages plus derived working memory and session digests."""

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

    def get_working_memory(self, session_id: str) -> Optional[str]:
        return self._get_summary_content(session_id, SESSION_SUMMARY_KIND_WORKING_MEMORY)

    def get_session_digest(self, session_id: str) -> Optional[str]:
        return self._get_summary_content(session_id, SESSION_SUMMARY_KIND_SESSION_DIGEST)

    def get_memory_snapshot(self, session_id: str) -> MemorySnapshot:
        records = self._list_summary_records(session_id)
        return self._build_snapshot_from_records(records)

    def append_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
    ) -> MemorySnapshot:
        try:
            session = self._get_or_create_session(session_id)
            turn_timestamp = utcnow()

            self._db.add_all(
                [
                    ChatMessage(
                        session_id=session_id,
                        role="user",
                        content=user_message,
                        created_at=turn_timestamp,
                    ),
                    ChatMessage(
                        session_id=session_id,
                        role="assistant",
                        content=assistant_message,
                        created_at=turn_timestamp,
                    ),
                ]
            )
            session.updated_at = turn_timestamp
            session.last_message_at = turn_timestamp
            session.message_count = max(session.message_count or 0, 0) + 2
            self._db.flush()

            snapshot = self.get_memory_snapshot(session_id)
            if self._summary_enabled:
                messages = self._list_messages(session_id)
                working_memory = self._build_working_memory(messages)
                session_digest = self.build_session_digest(
                    session_id=session_id,
                    messages=messages,
                    previous_digest=snapshot.session_digest,
                )
                snapshot = self._save_memory_snapshot(
                    session=session,
                    working_memory=working_memory,
                    session_digest=session_digest,
                )

            self._db.commit()
            return snapshot
        except Exception:
            self._db.rollback()
            raise

    def build_session_digest(
        self,
        session_id: str,
        messages: list[MemoryMessage],
        previous_digest: Optional[str] = None,
    ) -> Optional[str]:
        del session_id
        del previous_digest

        if not messages:
            return None

        if len(messages) <= 6:
            digest = self._render_message_snippets(messages, chars_per_message=80)
            return digest[: self._summary_max_chars] or None

        earlier = self._render_message_snippets(messages[:2], chars_per_message=70)
        recent = self._render_message_snippets(messages[-6:], chars_per_message=80)
        digest = f"Started with: {earlier} || Current state: {recent}".strip()
        return digest[: self._summary_max_chars] or None

    def _get_or_create_session(self, session_id: str) -> ChatSession:
        session = self._db.get(ChatSession, session_id)
        if session is None:
            session = ChatSession(id=session_id)
            self._db.add(session)
            self._db.flush()
        return session

    def _list_messages(self, session_id: str) -> list[MemoryMessage]:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        )
        return [self._to_memory_message(message) for message in self._db.scalars(stmt)]

    def _list_summary_records(self, session_id: str) -> list[SessionSummary]:
        stmt = (
            select(SessionSummary)
            .where(SessionSummary.session_id == session_id)
            .order_by(SessionSummary.updated_at.desc(), SessionSummary.id.desc())
        )
        return list(self._db.scalars(stmt))

    def _get_summary_content(
        self,
        session_id: str,
        kind: SessionSummaryKind,
    ) -> Optional[str]:
        stmt = select(SessionSummary).where(
            SessionSummary.session_id == session_id,
            SessionSummary.kind == kind,
        )
        summary = self._db.execute(stmt).scalar_one_or_none()
        return summary.content if summary else None

    def _save_memory_snapshot(
        self,
        session: ChatSession,
        *,
        working_memory: Optional[str],
        session_digest: Optional[str],
    ) -> MemorySnapshot:
        summary_timestamp = utcnow()
        working_memory_record = self._save_summary_kind(
            session=session,
            kind=SESSION_SUMMARY_KIND_WORKING_MEMORY,
            content=working_memory,
            summary_timestamp=summary_timestamp,
        )
        session_digest_record = self._save_summary_kind(
            session=session,
            kind=SESSION_SUMMARY_KIND_SESSION_DIGEST,
            content=session_digest,
            summary_timestamp=summary_timestamp,
        )

        if working_memory_record or session_digest_record:
            session.summary_updated_at = summary_timestamp
        else:
            session.summary_updated_at = None

        return MemorySnapshot(
            working_memory=working_memory_record.content if working_memory_record else None,
            session_digest=session_digest_record.content if session_digest_record else None,
            summary_updated_at=session.summary_updated_at,
        )

    def _save_summary_kind(
        self,
        *,
        session: ChatSession,
        kind: SessionSummaryKind,
        content: Optional[str],
        summary_timestamp: datetime,
    ) -> Optional[SessionSummary]:
        stmt = select(SessionSummary).where(
            SessionSummary.session_id == session.id,
            SessionSummary.kind == kind,
        )
        summary_record = self._db.execute(stmt).scalar_one_or_none()

        if not content:
            if summary_record is not None:
                self._db.delete(summary_record)
            return None

        if summary_record is None:
            summary_record = SessionSummary(
                session_id=session.id,
                kind=kind,
                content=content,
                updated_at=summary_timestamp,
            )
            self._db.add(summary_record)
        else:
            summary_record.content = content
            summary_record.updated_at = summary_timestamp

        return summary_record

    def _build_snapshot_from_records(self, records: list[SessionSummary]) -> MemorySnapshot:
        working_memory = None
        session_digest = None
        latest_updated_at = None

        for record in records:
            if latest_updated_at is None or record.updated_at > latest_updated_at:
                latest_updated_at = record.updated_at

            if record.kind == SESSION_SUMMARY_KIND_WORKING_MEMORY:
                working_memory = record.content
            elif record.kind == SESSION_SUMMARY_KIND_SESSION_DIGEST:
                session_digest = record.content

        return MemorySnapshot(
            working_memory=working_memory,
            session_digest=session_digest,
            summary_updated_at=latest_updated_at,
        )

    def _to_memory_message(self, message: ChatMessage) -> MemoryMessage:
        if message.role not in {"user", "assistant", "system"}:
            role = "system"
        else:
            role = message.role
        return MemoryMessage(role=role, content=message.content)

    def _build_working_memory(self, messages: list[MemoryMessage]) -> Optional[str]:
        if len(messages) <= self._short_window:
            return None

        older_messages = messages[:-self._short_window]
        working_memory = self._render_message_snippets(
            older_messages[-6:],
            chars_per_message=80,
        )
        return working_memory[: self._summary_max_chars] or None

    def _render_message_snippets(
        self,
        messages: list[MemoryMessage],
        *,
        chars_per_message: int,
    ) -> str:
        parts: list[str] = []
        for message in messages:
            speaker = self._speaker_name(message.role)
            cleaned_content = " ".join(message.content.split())
            if not cleaned_content:
                continue
            parts.append(f"{speaker}: {cleaned_content[:chars_per_message]}")
        return " | ".join(parts).strip()

    def _speaker_name(self, role: MessageRole) -> str:
        if role == "user":
            return "User"
        if role == "assistant":
            return "Assistant"
        return "System"
