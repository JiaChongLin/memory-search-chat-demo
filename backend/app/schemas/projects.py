from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


ProjectScopeMode = Literal[
    "conversation_only",
    "project_only",
    "project_plus_global",
    "global",
]
ProjectStatus = Literal["active", "archived", "deleted"]


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=4000)
    scope_mode: ProjectScopeMode = "conversation_only"
    is_isolated: bool = False


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    scope_mode: ProjectScopeMode
    is_isolated: bool
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime
