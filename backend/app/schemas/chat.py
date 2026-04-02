from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SearchSource(BaseModel):
    title: str
    url: str
    snippet: Optional[str] = None


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = Field(default=None, max_length=64)


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    title: Optional[str] = None
    working_memory: Optional[str] = None
    session_digest: Optional[str] = None
    used_live_model: bool = False
    fallback_reason: Optional[str] = None
    search_triggered: bool = False
    search_used: bool = False
    sources: list[SearchSource] = Field(default_factory=list)
    context_scope: Optional[str] = None
    related_session_digest_count: int = 0
    # Deprecated compatibility alias for older frontend builds that still read
    # related_summary_count. Internal naming should use related_session_digest_count.
    related_summary_count: Optional[int] = Field(
        default=None,
        json_schema_extra={"deprecated": True},
    )
