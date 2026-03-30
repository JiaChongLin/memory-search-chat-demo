from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domain.constants import (
    PROJECT_ACCESS_OPEN,
    ProjectAccessMode,
    RecordStatus,
)


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=4000)
    access_mode: ProjectAccessMode = PROJECT_ACCESS_OPEN


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    access_mode: ProjectAccessMode
    status: RecordStatus
    created_at: datetime
    updated_at: datetime


class ProjectDeleteResponse(BaseModel):
    success: bool = True
    project_id: int
    message: str
