from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domain.constants import RecordStatus


class SessionCreateRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)
    project_id: Optional[int] = None
    is_private: bool = False


class SessionUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)
    is_private: Optional[bool] = None


class SessionProjectMoveRequest(BaseModel):
    project_id: Optional[int] = None


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: Optional[str] = None
    project_id: Optional[int] = None
    status: RecordStatus
    is_private: bool
    last_message_at: Optional[datetime] = None
    message_count: int = 0
    summary_updated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class SessionSummaryResponse(BaseModel):
    session_id: str
    summary: Optional[str] = None
    summary_updated_at: Optional[datetime] = None


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: str
    role: str
    content: str
    created_at: datetime


class SessionDeleteResponse(BaseModel):
    success: bool = True
    session_id: str
    message: str
