from __future__ import annotations

from pydantic import BaseModel, Field


class SearchSource(BaseModel):
    title: str
    url: str
    snippet: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, max_length=64)


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    summary: str | None = None
    search_triggered: bool = False
    search_used: bool = False
    sources: list[SearchSource] = Field(default_factory=list)
