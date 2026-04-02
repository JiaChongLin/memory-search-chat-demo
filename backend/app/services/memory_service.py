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
SECTION_SESSION_TOPIC = "会话主题"
SECTION_KEY_CONCLUSIONS = "关键结论"
SECTION_CURRENT_STATUS = "当前状态"
SECTION_OPEN_QUESTIONS = "未决问题"


@dataclass
class MemoryMessage:
    role: MessageRole
    content: str


@dataclass
class MemorySnapshot:
    working_memory: Optional[str]
    session_digest: Optional[str]
    summary_updated_at: Optional[datetime] = None


@dataclass
class ConversationTurn:
    user_message: Optional[str]
    assistant_message: Optional[str]


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

        if not messages:
            return None

        turns = self._build_conversation_turns(messages)
        previous_sections = self._parse_digest_sections(previous_digest)

        topic = self._build_session_topic(messages, previous_topic=previous_sections[SECTION_SESSION_TOPIC])
        conclusions = self._merge_unique_items(
            self._extract_session_conclusions(messages, turns),
            previous_sections[SECTION_KEY_CONCLUSIONS],
            limit=4,
            chars_per_item=110,
        )
        current_status = self._merge_unique_items(
            self._extract_current_status(messages),
            previous_sections[SECTION_CURRENT_STATUS],
            limit=3,
            chars_per_item=120,
        )
        open_questions = self._merge_unique_items(
            self._extract_open_questions(turns),
            previous_sections[SECTION_OPEN_QUESTIONS],
            limit=3,
            chars_per_item=100,
        )

        return self._render_digest_sections(
            topic=topic,
            key_conclusions=conclusions,
            current_status=current_status,
            open_questions=open_questions,
        )

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
        turns = self._build_conversation_turns(older_messages)
        topic = self._build_recent_topic(older_messages)
        confirmed_items = self._merge_unique_items(
            self._extract_working_facts(older_messages, turns),
            limit=4,
            chars_per_item=90,
        )
        runtime_status = self._merge_unique_items(
            self._extract_handoff_status(older_messages),
            limit=3,
            chars_per_item=110,
        )
        open_questions = self._merge_unique_items(
            self._extract_open_questions(turns),
            limit=2,
            chars_per_item=90,
        )

        if not topic and not confirmed_items and not runtime_status and not open_questions:
            return None

        lines: list[str] = []
        if topic:
            lines.append(f"当前讨论主题：{topic}")
        if confirmed_items:
            lines.append("已确认信息：")
            lines.extend(f"- {item}" for item in confirmed_items)
        if runtime_status:
            lines.append("运行时状态：")
            lines.extend(f"- {item}" for item in runtime_status)
        if open_questions:
            lines.append("待继续关注：")
            lines.extend(f"- {item}" for item in open_questions)

        rendered = "\n".join(lines).strip()
        return self._finalize_summary(rendered)

    def _build_conversation_turns(self, messages: list[MemoryMessage]) -> list[ConversationTurn]:
        turns: list[ConversationTurn] = []
        pending_user: Optional[str] = None

        for message in messages:
            cleaned = self._clean_text(message.content)
            if not cleaned:
                continue

            if message.role == "user":
                if pending_user is not None:
                    turns.append(ConversationTurn(user_message=pending_user, assistant_message=None))
                pending_user = cleaned
                continue

            if message.role == "assistant":
                if pending_user is None:
                    turns.append(ConversationTurn(user_message=None, assistant_message=cleaned))
                else:
                    turns.append(ConversationTurn(user_message=pending_user, assistant_message=cleaned))
                    pending_user = None

        if pending_user is not None:
            turns.append(ConversationTurn(user_message=pending_user, assistant_message=None))

        return turns

    def _build_recent_topic(self, messages: list[MemoryMessage]) -> Optional[str]:
        user_messages = self._list_role_contents(messages, "user")
        if not user_messages:
            return None
        return self._truncate_text(user_messages[-1], 100)

    def _build_session_topic(
        self,
        messages: list[MemoryMessage],
        *,
        previous_topic: Optional[str] = None,
    ) -> Optional[str]:
        user_messages = self._list_role_contents(messages, "user")
        if not user_messages:
            return previous_topic

        first_topic = self._truncate_text(user_messages[0], 54)
        latest_topic = self._truncate_text(user_messages[-1], 86)
        if len(user_messages) == 1 or first_topic == latest_topic:
            return latest_topic
        return self._truncate_text(f"{first_topic} -> {latest_topic}", 110)

    def _extract_working_facts(
        self,
        messages: list[MemoryMessage],
        turns: list[ConversationTurn],
    ) -> list[str]:
        items: list[str] = []
        for message in messages:
            cleaned = self._clean_text(message.content)
            if not cleaned:
                continue
            if message.role == "user" and not self._looks_like_question(cleaned):
                items.append(cleaned)

        for turn in turns[-3:]:
            if turn.assistant_message:
                items.append(self._extract_answer_summary(turn.assistant_message))

        return items

    def _extract_session_conclusions(
        self,
        messages: list[MemoryMessage],
        turns: list[ConversationTurn],
    ) -> list[str]:
        items: list[str] = []

        for message in messages:
            cleaned = self._clean_text(message.content)
            if message.role == "user" and cleaned and not self._looks_like_question(cleaned):
                items.append(cleaned)

        for turn in turns:
            if turn.assistant_message:
                items.append(self._extract_answer_summary(turn.assistant_message))

        return items

    def _extract_handoff_status(self, messages: list[MemoryMessage]) -> list[str]:
        items: list[str] = []
        user_messages = self._list_role_contents(messages, "user")
        assistant_messages = self._list_role_contents(messages, "assistant")

        if user_messages:
            items.append(f"进入最近窗口前，用户主要关注：{self._truncate_text(user_messages[-1], 96)}")
        if assistant_messages:
            items.append(
                f"进入最近窗口前，助手已推进到：{self._truncate_text(self._extract_answer_summary(assistant_messages[-1]), 104)}"
            )
        return items

    def _extract_current_status(self, messages: list[MemoryMessage]) -> list[str]:
        items: list[str] = []
        user_messages = self._list_role_contents(messages, "user")
        assistant_messages = self._list_role_contents(messages, "assistant")

        if user_messages:
            items.append(f"最新用户关注：{self._truncate_text(user_messages[-1], 100)}")
        if assistant_messages:
            items.append(
                f"最新助手回复：{self._truncate_text(self._extract_answer_summary(assistant_messages[-1]), 116)}"
            )
        return items

    def _extract_open_questions(self, turns: list[ConversationTurn]) -> list[str]:
        items: list[str] = []
        for turn in turns[-4:]:
            user_message = turn.user_message
            if not user_message or not self._looks_like_question(user_message):
                continue
            if turn.assistant_message is None or self._assistant_reply_feels_incomplete(turn.assistant_message):
                items.append(user_message)
        return items

    def _assistant_reply_feels_incomplete(self, content: str) -> bool:
        lowered = content.lower()
        markers = (
            "无法",
            "不能",
            "不清楚",
            "不确定",
            "需要更多",
            "未提供",
            "暂时",
            "建议访问",
            "建议提供",
            "无法实时",
            "missing_api_key",
            "provider_request_failed",
        )
        return any(marker in content or marker in lowered for marker in markers)

    def _parse_digest_sections(self, digest: Optional[str]) -> dict[str, object]:
        sections: dict[str, object] = {
            SECTION_SESSION_TOPIC: None,
            SECTION_KEY_CONCLUSIONS: [],
            SECTION_CURRENT_STATUS: [],
            SECTION_OPEN_QUESTIONS: [],
        }
        if not digest:
            return sections

        current_section: Optional[str] = None
        for raw_line in digest.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith(f"{SECTION_SESSION_TOPIC}："):
                sections[SECTION_SESSION_TOPIC] = line.split("：", 1)[1].strip() or None
                current_section = None
                continue
            if line == f"{SECTION_KEY_CONCLUSIONS}：":
                current_section = SECTION_KEY_CONCLUSIONS
                continue
            if line == f"{SECTION_CURRENT_STATUS}：":
                current_section = SECTION_CURRENT_STATUS
                continue
            if line == f"{SECTION_OPEN_QUESTIONS}：":
                current_section = SECTION_OPEN_QUESTIONS
                continue
            if current_section and line.startswith("- "):
                cast_list = sections[current_section]
                if isinstance(cast_list, list):
                    cast_list.append(line[2:].strip())

        return sections

    def _render_digest_sections(
        self,
        *,
        topic: Optional[str],
        key_conclusions: list[str],
        current_status: list[str],
        open_questions: list[str],
    ) -> Optional[str]:
        if not topic and not key_conclusions and not current_status and not open_questions:
            return None

        lines: list[str] = []
        if topic:
            lines.append(f"{SECTION_SESSION_TOPIC}：{topic}")
        if key_conclusions:
            lines.append(f"{SECTION_KEY_CONCLUSIONS}：")
            lines.extend(f"- {item}" for item in key_conclusions)
        if current_status:
            lines.append(f"{SECTION_CURRENT_STATUS}：")
            lines.extend(f"- {item}" for item in current_status)
        if open_questions:
            lines.append(f"{SECTION_OPEN_QUESTIONS}：")
            lines.extend(f"- {item}" for item in open_questions)

        rendered = "\n".join(lines).strip()
        return self._finalize_summary(rendered)

    def _merge_unique_items(
        self,
        *groups: list[str],
        limit: int,
        chars_per_item: int = 100,
    ) -> list[str]:
        seen: set[str] = set()
        items: list[str] = []
        for group in groups:
            for item in group:
                normalized = self._clean_text(item)
                if not normalized:
                    continue
                dedupe_key = normalized.casefold()
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                items.append(self._truncate_text(normalized, chars_per_item))
                if len(items) >= limit:
                    return items
        return items

    def _list_role_contents(self, messages: list[MemoryMessage], role: MessageRole) -> list[str]:
        contents: list[str] = []
        for message in messages:
            if message.role != role:
                continue
            cleaned = self._clean_text(message.content)
            if cleaned:
                contents.append(cleaned)
        return contents

    def _extract_answer_summary(self, content: str) -> str:
        cleaned = self._clean_text(content)
        if not cleaned:
            return ""

        separators = ["。", "！", "？", ". ", "! ", "? ", "\n", "；", ";"]
        earliest_cut = len(cleaned)
        for separator in separators:
            index = cleaned.find(separator)
            if index > 0:
                earliest_cut = min(earliest_cut, index + len(separator.strip()))
        first_chunk = cleaned[:earliest_cut].strip()
        return self._truncate_text(first_chunk or cleaned, 120)

    def _looks_like_question(self, content: str) -> bool:
        stripped = content.strip()
        lowered = stripped.lower()
        question_markers = (
            "?",
            "？",
            "吗",
            "么",
            "什么",
            "谁",
            "哪",
            "哪些",
            "多少",
            "为何",
            "为什么",
            "如何",
            "怎么",
            "是否",
            "能否",
            "可否",
            "请问",
        )
        return any(marker in stripped or marker in lowered for marker in question_markers)

    def _clean_text(self, value: str) -> str:
        return " ".join(value.split())

    def _truncate_text(self, value: str, limit: int) -> str:
        cleaned = self._clean_text(value)
        if len(cleaned) <= limit:
            return cleaned
        return f"{cleaned[: max(0, limit - 1)].rstrip()}…"

    def _finalize_summary(self, content: str) -> Optional[str]:
        trimmed = content.strip()
        if not trimmed:
            return None
        if len(trimmed) <= self._summary_max_chars:
            return trimmed
        return f"{trimmed[: max(0, self._summary_max_chars - 1)].rstrip()}…"
