from __future__ import annotations

from uuid import uuid4

from fastapi import Depends
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.db.session import get_db
from backend.app.schemas.chat import ChatRequest, ChatResponse, SearchSource
from backend.app.services.context_resolver import ContextResolver
from backend.app.services.llm_service import LLMService
from backend.app.services.memory_service import MemoryService
from backend.app.services.search_service import SearchService
from backend.app.services.session_service import SessionService


class ChatService:
    """Coordinate context resolution, search, model calls, and persistence."""

    def __init__(
        self,
        memory_service: MemoryService,
        context_resolver: ContextResolver,
        session_service: SessionService,
        search_service: SearchService,
        llm_service: LLMService,
    ) -> None:
        self._memory_service = memory_service
        self._context_resolver = context_resolver
        self._session_service = session_service
        self._search_service = search_service
        self._llm_service = llm_service

    def handle_chat(self, payload: ChatRequest) -> ChatResponse:
        session_id = payload.session_id or self._create_session_id()
        resolved_context = self._context_resolver.resolve_context(
            session_id,
            allow_missing=payload.session_id is None,
        )

        search_triggered = self._search_service.should_search(payload.message)
        search_results = (
            self._search_service.search(payload.message) if search_triggered else []
        )

        llm_reply = self._llm_service.generate_reply(
            user_message=payload.message,
            history=resolved_context.recent_messages,
            session_summary=resolved_context.context_summary,
            search_results=search_results,
        )

        updated_summary = self._memory_service.append_turn(
            session_id=session_id,
            user_message=payload.message,
            assistant_message=llm_reply.content,
        )

        session_title = None
        try:
            session = self._session_service.maybe_generate_title(
                session_id,
                fallback_user_message=payload.message,
            )
            session_title = session.title
        except Exception:
            session_title = None

        return ChatResponse(
            session_id=session_id,
            reply=llm_reply.content,
            title=session_title,
            summary=updated_summary,
            used_live_model=llm_reply.used_live_model,
            fallback_reason=llm_reply.fallback_reason,
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
            context_scope=resolved_context.context_scope,
            related_summary_count=len(resolved_context.related_summaries),
        )

    def _create_session_id(self) -> str:
        return uuid4().hex


def get_chat_service(db: Session = Depends(get_db)) -> ChatService:
    settings = get_settings()

    memory_service = MemoryService(
        db=db,
        short_window=settings.memory_short_window,
        summary_enabled=settings.memory_summary_enabled,
        summary_max_chars=settings.memory_summary_max_chars,
    )
    context_resolver = ContextResolver(db=db, memory_service=memory_service)
    session_service = SessionService(db=db)
    search_service = SearchService(settings=settings)
    llm_service = LLMService(settings=settings)

    return ChatService(
        memory_service=memory_service,
        context_resolver=context_resolver,
        session_service=session_service,
        search_service=search_service,
        llm_service=llm_service,
    )
