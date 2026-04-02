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
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-facing project name. Weak prompt signal only.",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=4000,
        description="Human-readable project note shown in UI. Never injected into model context.",
    )
    instruction: Optional[str] = Field(
        default=None,
        max_length=4000,
        description="Project-level model instruction. Primary prompt text for chats in this project.",
    )
    access_mode: ProjectAccessMode = PROJECT_ACCESS_OPEN


class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Human-facing project name. Weak prompt signal only.",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=4000,
        description="Human-readable project note shown in UI. Never injected into model context.",
    )
    instruction: Optional[str] = Field(
        default=None,
        max_length=4000,
        description="Project-level model instruction. Primary prompt text for chats in this project.",
    )


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = Field(
        default=None,
        description="Human-readable project note for UI display only; excluded from model context.",
    )
    instruction: Optional[str] = Field(
        default=None,
        description="Project-level instruction used by the model during chats in this project.",
    )
    access_mode: ProjectAccessMode
    status: RecordStatus
    created_at: datetime
    updated_at: datetime


class ProjectDeleteResponse(BaseModel):
    success: bool = True
    project_id: int
    message: str


class StableFactCreateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)


class StableFactUpdateRequest(BaseModel):
    content: Optional[str] = Field(default=None, max_length=4000)
    status: Optional[RecordStatus] = None


class StableFactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    content: str
    status: RecordStatus
    created_at: datetime
    updated_at: datetime


class StableFactDeleteResponse(BaseModel):
    success: bool = True
    stable_fact_id: int
    message: str
