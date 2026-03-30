from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


SessionStatus = Literal["active", "archived", "deleted"]


class SessionCreateRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)
    project_id: Optional[int] = None
    is_private: bool = False


class SessionProjectMoveRequest(BaseModel):
    project_id: int


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: Optional[str] = None
    project_id: Optional[int] = None
    status: SessionStatus
    is_private: bool
    created_at: datetime
    updated_at: datetime
