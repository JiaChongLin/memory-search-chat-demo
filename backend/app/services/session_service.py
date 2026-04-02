from __future__ import annotations

import re
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import ChatMessage, ChatSession, Project, utcnow
from backend.app.domain.constants import (
    RECORD_STATUSES,
    SESSION_SUMMARY_KIND_SESSION_DIGEST,
    SESSION_SUMMARY_KIND_WORKING_MEMORY,
    STATUS_ACTIVE,
    STATUS_ARCHIVED,
)
from backend.app.schemas.sessions import (
    SessionCreateRequest,
    SessionProjectMoveRequest,
    SessionUpdateRequest,
)

_TITLE_MAX_LENGTH = 36


class SessionService:
    """Handle lightweight session management operations."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create_session(self, payload: SessionCreateRequest) -> ChatSession:
        if payload.project_id is not None:
            self._get_project_or_404(payload.project_id)

        chat_session = ChatSession(
            id=uuid4().hex,
            title=self._normalize_title(payload.title),
            project_id=payload.project_id,
            is_private=payload.is_private,
            status=STATUS_ACTIVE,
        )
        self._db.add(chat_session)
        self._db.commit()
        self._db.refresh(chat_session)
        return chat_session

    def list_sessions(
        self,
        *,
        project_id: int | None = None,
        include_archived: bool = False,
    ) -> list[ChatSession]:
        stmt = select(ChatSession).order_by(
            ChatSession.updated_at.desc(),
            ChatSession.created_at.desc(),
        )
        if project_id is not None:
            stmt = stmt.where(ChatSession.project_id == project_id)
        if include_archived:
            stmt = stmt.where(ChatSession.status.in_(RECORD_STATUSES))
        else:
            stmt = stmt.where(ChatSession.status == STATUS_ACTIVE)
        return list(self._db.scalars(stmt))

    def get_session(self, session_id: str) -> ChatSession:
        return self._get_session_or_404(session_id)

    def get_session_summary(
        self,
        session_id: str,
    ) -> tuple[str | None, str | None, datetime | None]:
        chat_session = self._get_session_or_404(session_id)
        working_memory = self._get_summary_content(
            chat_session,
            SESSION_SUMMARY_KIND_WORKING_MEMORY,
        )
        session_digest = self._get_summary_content(
            chat_session,
            SESSION_SUMMARY_KIND_SESSION_DIGEST,
        )
        return working_memory, session_digest, chat_session.summary_updated_at

    def get_session_messages(self, session_id: str) -> list[ChatMessage]:
        self._get_session_or_404(session_id)
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        )
        return list(self._db.scalars(stmt))

    def rollback_latest_turn(self, session_id: str) -> str:
        session = self._get_session_for_latest_turn_or_409(session_id)
        user_message, assistant_message = self._get_latest_turn_pair_or_409(session_id)

        latest_user_content = user_message.content
        self._db.delete(assistant_message)
        self._db.delete(user_message)
        self._db.flush()
        self._refresh_message_metadata(session)
        self._db.flush()
        return latest_user_content

    def update_session(
        self,
        session_id: str,
        payload: SessionUpdateRequest,
    ) -> ChatSession:
        chat_session = self._get_session_or_404(session_id)
        changes = payload.model_dump(exclude_unset=True)

        if "title" in changes:
            chat_session.title = self._normalize_title(payload.title)
        if "is_private" in changes and payload.is_private is not None:
            chat_session.is_private = payload.is_private

        if changes:
            chat_session.updated_at = utcnow()
            self._db.commit()
            self._db.refresh(chat_session)
        return chat_session

    def archive_session(self, session_id: str) -> ChatSession:
        chat_session = self._get_session_or_404(session_id)
        chat_session.status = STATUS_ARCHIVED
        chat_session.updated_at = utcnow()
        self._db.commit()
        self._db.refresh(chat_session)
        return chat_session

    def delete_session(self, session_id: str) -> str:
        chat_session = self._get_session_or_404(session_id)
        deleted_session_id = chat_session.id
        self._db.delete(chat_session)
        self._db.commit()
        return deleted_session_id

    def move_session_to_project(
        self,
        session_id: str,
        payload: SessionProjectMoveRequest,
    ) -> ChatSession:
        chat_session = self._get_session_or_404(session_id)
        if payload.project_id is not None:
            project = self._get_project_or_404(payload.project_id)
            chat_session.project_id = project.id
        else:
            chat_session.project_id = None

        chat_session.updated_at = utcnow()
        self._db.commit()
        self._db.refresh(chat_session)
        return chat_session

    def maybe_generate_title(
        self,
        session_id: str,
        fallback_user_message: str | None = None,
    ) -> ChatSession:
        chat_session = self._get_session_or_404(session_id)
        if self._normalize_title(chat_session.title):
            return chat_session

        stmt = (
            select(ChatMessage.content)
            .where(
                ChatMessage.session_id == session_id,
                ChatMessage.role == "user",
            )
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        )
        first_user_message = self._db.execute(stmt).scalars().first()
        generated_title = self.generate_default_title(
            first_user_message or fallback_user_message,
        )
        if not generated_title:
            return chat_session

        chat_session.title = generated_title
        chat_session.updated_at = utcnow()
        self._db.commit()
        self._db.refresh(chat_session)
        return chat_session

    def generate_default_title(self, source_text: str | None) -> str | None:
        normalized = self._normalize_title(source_text)
        if not normalized:
            return None

        first_segment = re.split(r"[。！？!?;；\n]+", normalized, maxsplit=1)[0].strip()
        candidate = first_segment or normalized
        candidate = re.sub(r"^[\-–—:：,，.。!?！？\s]+", "", candidate).strip()
        if not candidate:
            return None

        if len(candidate) <= _TITLE_MAX_LENGTH:
            return candidate

        shortened = candidate[: _TITLE_MAX_LENGTH - 1].rstrip(" ,，、.。!?！？")
        return f"{shortened}…"

    def _normalize_title(self, title: str | None) -> str | None:
        if title is None:
            return None
        normalized = " ".join(title.split()).strip()
        return normalized or None

    def _get_summary_content(self, chat_session: ChatSession, kind: str) -> str | None:
        for record in chat_session.summaries:
            if record.kind == kind:
                return record.content
        return None

    def _get_project_or_404(self, project_id: int) -> Project:
        project = self._db.get(Project, project_id)
        if project is None or project.status != STATUS_ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found.",
            )
        return project

    def _get_session_or_404(self, session_id: str) -> ChatSession:
        chat_session = self._db.get(ChatSession, session_id)
        if chat_session is None or chat_session.status not in RECORD_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found.",
            )
        return chat_session

    def _get_session_for_latest_turn_or_409(self, session_id: str) -> ChatSession:
        chat_session = self._db.get(ChatSession, session_id)
        if chat_session is None or chat_session.status != STATUS_ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Latest-turn actions require an existing active session.",
            )
        return chat_session

    def _get_latest_turn_pair_or_409(
        self,
        session_id: str,
    ) -> tuple[ChatMessage, ChatMessage]:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(2)
        )
        latest_messages = list(self._db.scalars(stmt))
        if len(latest_messages) < 2:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No latest turn is available for regenerate or edit.",
            )

        assistant_message, user_message = latest_messages
        if user_message.role != "user" or assistant_message.role != "assistant":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Latest turn must end with a user -> assistant pair.",
            )

        return user_message, assistant_message

    def _refresh_message_metadata(self, chat_session: ChatSession) -> None:
        stmt = (
            select(ChatMessage.created_at)
            .where(ChatMessage.session_id == chat_session.id)
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        )
        created_ats = list(self._db.execute(stmt).scalars())
        chat_session.message_count = len(created_ats)
        chat_session.last_message_at = created_ats[0] if created_ats else None

