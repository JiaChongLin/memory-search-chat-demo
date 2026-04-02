from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.chat import ChatResponse, ErrorResponse
from backend.app.schemas.sessions import (
    LatestTurnEditRequest,
    MessageResponse,
    SessionCreateRequest,
    SessionDeleteResponse,
    SessionProjectMoveRequest,
    SessionResponse,
    SessionSummaryResponse,
    SessionUpdateRequest,
)
from backend.app.services.chat_service import ChatService, get_chat_service
from backend.app.services.session_service import SessionService


router = APIRouter()


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
    chat_session = SessionService(db).create_session(payload)
    return SessionResponse.model_validate(chat_session)


@router.get(
    "",
    response_model=list[SessionResponse],
    summary="List sessions",
)
def list_sessions(
    project_id: Optional[int] = Query(default=None),
    include_archived: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[SessionResponse]:
    sessions = SessionService(db).list_sessions(
        project_id=project_id,
        include_archived=include_archived,
    )
    return [SessionResponse.model_validate(chat_session) for chat_session in sessions]


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
    chat_session = SessionService(db).get_session(session_id)
    return SessionResponse.model_validate(chat_session)


@router.get(
    "/{session_id}/summary",
    response_model=SessionSummaryResponse,
    summary="Get derived memory state for a session",
    responses={404: {"model": ErrorResponse}},
)
def get_session_summary(
    session_id: str,
    db: Session = Depends(get_db),
) -> SessionSummaryResponse:
    working_memory, session_digest, summary_updated_at = SessionService(db).get_session_summary(
        session_id
    )
    return SessionSummaryResponse(
        session_id=session_id,
        working_memory=working_memory,
        session_digest=session_digest,
        summary_updated_at=summary_updated_at,
    )


@router.get(
    "/{session_id}/messages",
    response_model=list[MessageResponse],
    summary="Get full session message history",
    responses={404: {"model": ErrorResponse}},
)
def get_session_messages(
    session_id: str,
    db: Session = Depends(get_db),
) -> list[MessageResponse]:
    messages = SessionService(db).get_session_messages(session_id)
    return [MessageResponse.model_validate(message) for message in messages]


@router.post(
    "/{session_id}/latest-turn/regenerate",
    response_model=ChatResponse,
    summary="Regenerate the latest user -> assistant turn",
    responses={409: {"model": ErrorResponse}},
)
def regenerate_latest_turn(
    session_id: str,
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    return chat_service.regenerate_latest_turn(session_id)


@router.post(
    "/{session_id}/latest-turn/edit",
    response_model=ChatResponse,
    summary="Edit the latest user message and regenerate the turn",
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def edit_latest_turn(
    session_id: str,
    payload: LatestTurnEditRequest,
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    return chat_service.edit_latest_turn(session_id, payload.message)


@router.patch(
    "/{session_id}",
    response_model=SessionResponse,
    summary="Update a session",
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def update_session(
    session_id: str,
    payload: SessionUpdateRequest,
    db: Session = Depends(get_db),
) -> SessionResponse:
    chat_session = SessionService(db).update_session(session_id, payload)
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
    chat_session = SessionService(db).archive_session(session_id)
    return SessionResponse.model_validate(chat_session)


@router.delete(
    "/{session_id}",
    response_model=SessionDeleteResponse,
    summary="Delete a session",
    responses={404: {"model": ErrorResponse}},
)
def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
) -> SessionDeleteResponse:
    deleted_session_id = SessionService(db).delete_session(session_id)
    return SessionDeleteResponse(
        session_id=deleted_session_id,
        message="Session deleted.",
    )


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
    chat_session = SessionService(db).move_session_to_project(session_id, payload)
    return SessionResponse.model_validate(chat_session)
