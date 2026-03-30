from __future__ import annotations

from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import ChatSession, Project, utcnow
from backend.app.domain.constants import STATUS_ARCHIVED, STATUS_DELETED
from backend.app.schemas.sessions import SessionCreateRequest, SessionProjectMoveRequest


class SessionService:
    """Handle lightweight session management operations."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create_session(self, payload: SessionCreateRequest) -> ChatSession:
        if payload.project_id is not None:
            self._get_project_or_404(payload.project_id)

        chat_session = ChatSession(
            id=uuid4().hex,
            title=payload.title,
            project_id=payload.project_id,
            is_private=payload.is_private,
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
        include_deleted: bool = False,
    ) -> list[ChatSession]:
        stmt = select(ChatSession).order_by(
            ChatSession.updated_at.desc(),
            ChatSession.created_at.desc(),
        )
        if project_id is not None:
            stmt = stmt.where(ChatSession.project_id == project_id)
        if not include_archived:
            stmt = stmt.where(ChatSession.status != STATUS_ARCHIVED)
        if not include_deleted:
            stmt = stmt.where(ChatSession.status != STATUS_DELETED)
        return list(self._db.scalars(stmt))

    def get_session(self, session_id: str) -> ChatSession:
        return self._get_session_or_404(session_id)

    def archive_session(self, session_id: str) -> ChatSession:
        chat_session = self._get_session_or_404(session_id)
        chat_session.status = STATUS_ARCHIVED
        chat_session.updated_at = utcnow()
        self._db.commit()
        self._db.refresh(chat_session)
        return chat_session

    def soft_delete_session(self, session_id: str) -> ChatSession:
        chat_session = self._get_session_or_404(session_id)
        chat_session.status = STATUS_DELETED
        chat_session.updated_at = utcnow()
        self._db.commit()
        self._db.refresh(chat_session)
        return chat_session

    def move_session_to_project(
        self,
        session_id: str,
        payload: SessionProjectMoveRequest,
    ) -> ChatSession:
        chat_session = self._get_session_or_404(session_id)
        project = self._get_project_or_404(payload.project_id)

        chat_session.project_id = project.id
        chat_session.updated_at = utcnow()
        self._db.commit()
        self._db.refresh(chat_session)
        return chat_session

    def _get_project_or_404(self, project_id: int) -> Project:
        project = self._db.get(Project, project_id)
        if project is None or project.status == STATUS_DELETED:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found.",
            )
        return project

    def _get_session_or_404(self, session_id: str) -> ChatSession:
        chat_session = self._db.get(ChatSession, session_id)
        if chat_session is None or chat_session.status == STATUS_DELETED:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found.",
            )
        return chat_session
