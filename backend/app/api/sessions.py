from __future__ import annotations

from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import ChatSession, Project, utcnow
from backend.app.db.session import get_db
from backend.app.schemas.chat import ErrorResponse
from backend.app.schemas.sessions import (
    SessionCreateRequest,
    SessionProjectMoveRequest,
    SessionResponse,
)


router = APIRouter()


def _get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.status == "deleted":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
    return project


def _get_session_or_404(
    db: Session,
    session_id: str,
    *,
    allow_deleted: bool = False,
) -> ChatSession:
    chat_session = db.get(ChatSession, session_id)
    if chat_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found.",
        )
    if not allow_deleted and chat_session.status == "deleted":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found.",
        )
    return chat_session


@router.post(
    "",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a session",
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def create_session(
    payload: SessionCreateRequest,
    db: Session = Depends(get_db),
) -> SessionResponse:
    if payload.project_id is not None:
        _get_project_or_404(db, payload.project_id)

    chat_session = ChatSession(
        id=uuid4().hex,
        title=payload.title,
        project_id=payload.project_id,
        is_private=payload.is_private,
    )
    db.add(chat_session)
    db.commit()
    db.refresh(chat_session)
    return SessionResponse.model_validate(chat_session)


@router.get(
    "",
    response_model=list[SessionResponse],
    summary="List sessions",
)
def list_sessions(
    project_id: Optional[int] = Query(default=None),
    include_archived: bool = Query(default=False),
    include_deleted: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[SessionResponse]:
    stmt = select(ChatSession).order_by(
        ChatSession.updated_at.desc(),
        ChatSession.created_at.desc(),
    )
    if project_id is not None:
        stmt = stmt.where(ChatSession.project_id == project_id)
    if not include_archived:
        stmt = stmt.where(ChatSession.status != "archived")
    if not include_deleted:
        stmt = stmt.where(ChatSession.status != "deleted")

    return [SessionResponse.model_validate(chat_session) for chat_session in db.scalars(stmt)]


@router.get(
    "/{session_id}",
    response_model=SessionResponse,
    summary="Get a session",
    responses={404: {"model": ErrorResponse}},
)
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
) -> SessionResponse:
    chat_session = _get_session_or_404(db, session_id)
    return SessionResponse.model_validate(chat_session)


@router.post(
    "/{session_id}/archive",
    response_model=SessionResponse,
    summary="Archive a session",
    responses={404: {"model": ErrorResponse}},
)
def archive_session(
    session_id: str,
    db: Session = Depends(get_db),
) -> SessionResponse:
    chat_session = _get_session_or_404(db, session_id)
    chat_session.status = "archived"
    chat_session.updated_at = utcnow()
    db.commit()
    db.refresh(chat_session)
    return SessionResponse.model_validate(chat_session)


@router.delete(
    "/{session_id}",
    response_model=SessionResponse,
    summary="Soft delete a session",
    responses={404: {"model": ErrorResponse}},
)
def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
) -> SessionResponse:
    chat_session = _get_session_or_404(db, session_id)
    chat_session.status = "deleted"
    chat_session.updated_at = utcnow()
    db.commit()
    db.refresh(chat_session)
    return SessionResponse.model_validate(chat_session)


@router.post(
    "/{session_id}/move",
    response_model=SessionResponse,
    summary="Move a session into a project",
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def move_session_to_project(
    session_id: str,
    payload: SessionProjectMoveRequest,
    db: Session = Depends(get_db),
) -> SessionResponse:
    chat_session = _get_session_or_404(db, session_id)
    project = _get_project_or_404(db, payload.project_id)

    chat_session.project_id = project.id
    chat_session.updated_at = utcnow()
    db.commit()
    db.refresh(chat_session)
    return SessionResponse.model_validate(chat_session)
