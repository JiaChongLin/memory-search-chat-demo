from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import ChatMessage, ChatSession, SessionSummary, utcnow


MessageRole = Literal["user", "assistant", "system"]


@dataclass
class MemoryMessage:
    role: MessageRole
    content: str


class MemoryService:
    """负责会话记忆的读取、写入和简化摘要更新。"""

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

    def get_summary(self, session_id: str) -> Optional[str]:
        stmt = select(SessionSummary).where(SessionSummary.session_id == session_id)
        summary = self._db.execute(stmt).scalar_one_or_none()
        return summary.content if summary else None

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
            role: MessageRole = "system"
        else:
            role = message.role
        return MemoryMessage(role=role, content=message.content)

    def _build_summary(self, messages: list[MemoryMessage]) -> Optional[str]:
        if len(messages) <= self._short_window:
            return None

        # 只压缩较早的消息，保留最近几轮给模型直接参考。
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
