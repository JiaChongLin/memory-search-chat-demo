from __future__ import annotations

from functools import lru_cache
from uuid import uuid4

from backend.app.core.config import get_settings
from backend.app.schemas.chat import ChatRequest, ChatResponse, SearchSource
from backend.app.services.llm_service import LLMService
from backend.app.services.memory_service import MemoryService
from backend.app.services.search_service import SearchService


class ChatService:
    """Coordinates memory, search, and model invocation for each chat turn."""

    def __init__(
        self,
        memory_service: MemoryService,
        search_service: SearchService,
        llm_service: LLMService,
    ) -> None:
        self._memory_service = memory_service
        self._search_service = search_service
        self._llm_service = llm_service

    def handle_chat(self, payload: ChatRequest) -> ChatResponse:
        session_id = payload.session_id or self._create_session_id()

        recent_messages = self._memory_service.get_recent_messages(session_id)
        session_summary = self._memory_service.get_summary(session_id)

        search_triggered = self._search_service.should_search(payload.message)
        search_results = (
            self._search_service.search(payload.message) if search_triggered else []
        )

        llm_reply = self._llm_service.generate_reply(
            user_message=payload.message,
            history=recent_messages,
            session_summary=session_summary,
            search_results=search_results,
        )

        updated_summary = self._memory_service.append_turn(
            session_id=session_id,
            user_message=payload.message,
            assistant_message=llm_reply.content,
        )

        return ChatResponse(
            session_id=session_id,
            reply=llm_reply.content,
            summary=updated_summary,
            search_triggered=search_triggered,
            search_used=bool(search_results),
            sources=[
                SearchSource(
                    title=result.title,
                    url=result.url,
                    snippet=result.snippet,
                )
                for result in search_results
            ],
        )

    def _create_session_id(self) -> str:
        return uuid4().hex


@lru_cache(maxsize=1)
def get_chat_service() -> ChatService:
    settings = get_settings()

    memory_service = MemoryService(
        short_window=settings.memory_short_window,
        summary_enabled=settings.memory_summary_enabled,
        summary_max_chars=settings.memory_summary_max_chars,
    )
    search_service = SearchService(settings=settings)
    llm_service = LLMService(settings=settings)

    return ChatService(
        memory_service=memory_service,
        search_service=search_service,
        llm_service=llm_service,
    )
