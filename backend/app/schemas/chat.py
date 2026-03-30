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
    summary: Optional[str] = None
    used_live_model: bool = False
    fallback_reason: Optional[str] = None
    search_triggered: bool = False
    search_used: bool = False
    sources: list[SearchSource] = Field(default_factory=list)
