from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


MessageRole = Literal["user", "assistant", "system"]


@dataclass(slots=True)
class MemoryMessage:
    role: MessageRole
    content: str


@dataclass(slots=True)
class SessionState:
    session_id: str
    messages: list[MemoryMessage] = field(default_factory=list)
    summary: str | None = None


class MemoryService:
    """Keeps a lightweight in-memory representation of conversation state."""

    def __init__(
        self,
        short_window: int = 6,
        summary_enabled: bool = True,
        summary_max_chars: int = 600,
    ) -> None:
        self._short_window = max(2, short_window)
        self._summary_enabled = summary_enabled
        self._summary_max_chars = max(120, summary_max_chars)
        self._sessions: dict[str, SessionState] = {}

    def get_recent_messages(self, session_id: str) -> list[MemoryMessage]:
        state = self._get_or_create_state(session_id)
        return list(state.messages[-self._short_window :])

    def get_summary(self, session_id: str) -> str | None:
        return self._get_or_create_state(session_id).summary

    def append_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
    ) -> str | None:
        state = self._get_or_create_state(session_id)
        state.messages.append(MemoryMessage(role="user", content=user_message))
        state.messages.append(MemoryMessage(role="assistant", content=assistant_message))

        if self._summary_enabled:
            state.summary = self._build_summary(state.messages)

        return state.summary

    def _get_or_create_state(self, session_id: str) -> SessionState:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState(session_id=session_id)
        return self._sessions[session_id]

    def _build_summary(self, messages: list[MemoryMessage]) -> str | None:
        if len(messages) <= self._short_window:
            return None

        older_messages = messages[:-self._short_window]
        condensed_parts: list[str] = []

        for message in older_messages[-6:]:
            speaker = "用户" if message.role == "user" else "助手"
            cleaned_content = " ".join(message.content.split())
            condensed_parts.append(f"{speaker}: {cleaned_content[:80]}")

        summary = " | ".join(condensed_parts).strip()
        return summary[: self._summary_max_chars] or None
