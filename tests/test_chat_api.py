from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.app.main as main_module
from backend.app.core.config import Settings
from backend.app.db.models import Base
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.services.chat_service import ChatService, get_chat_service
from backend.app.services.context_resolver import ContextResolver
from backend.app.services.llm_service import LLMService
from backend.app.services.memory_service import MemoryService
from backend.app.services.search_service import SearchResult, SearchService


@pytest.fixture
def client(monkeypatch):
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    db_path = temp_dir / f"chat_api_test_{uuid4().hex}.db"

    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    Base.metadata.create_all(bind=engine)

    settings = Settings(
        app_name="memory-search-chat-demo",
        app_env="test",
        api_prefix="/api",
        database_url=f"sqlite:///{db_path.as_posix()}",
        llm_provider="dashscope",
        llm_api_key="",
        llm_model="qwen-plus",
        llm_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        llm_timeout_seconds=30,
        llm_fallback_enabled=True,
        memory_short_window=6,
        memory_summary_enabled=True,
        memory_summary_max_chars=600,
        search_enabled=True,
        search_provider="duckduckgo",
        search_base_url="https://html.duckduckgo.com/html/",
        search_timeout_seconds=15,
        search_max_results=5,
    )

    monkeypatch.setattr(main_module, "init_db", lambda: None)

    def override_chat_service():
        db = testing_session_local()
        try:
            memory_service = MemoryService(
                db=db,
                short_window=settings.memory_short_window,
                summary_enabled=settings.memory_summary_enabled,
                summary_max_chars=settings.memory_summary_max_chars,
            )
            yield ChatService(
                memory_service=memory_service,
                context_resolver=ContextResolver(db=db, memory_service=memory_service),
                search_service=SearchService(settings=settings),
                llm_service=LLMService(settings=settings),
            )
        finally:
            db.close()

    def override_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_chat_service] = override_chat_service
    app.dependency_overrides[get_db] = override_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    engine.dispose()
    if db_path.exists():
        db_path.unlink()


def test_chat_first_request_returns_session_and_reply(client: TestClient) -> None:
    response = client.post("/api/chat", json={"message": "hello demo"})

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"]
    assert data["reply"]
    assert data["used_live_model"] is False
    assert data["fallback_reason"] == "missing_api_key"
    assert data["search_used"] is False
    assert isinstance(data["sources"], list)
    assert data["context_scope"] == "open"
    assert data["related_summary_count"] == 0


def test_chat_reuses_existing_session(client: TestClient) -> None:
    first_response = client.post("/api/chat", json={"message": "remember my name is tom"})
    first_data = first_response.json()

    second_response = client.post(
        "/api/chat",
        json={
            "message": "what did I just say",
            "session_id": first_data["session_id"],
        },
    )

    assert second_response.status_code == 200
    second_data = second_response.json()
    assert second_data["session_id"] == first_data["session_id"]
    assert second_data["reply"]
    assert second_data["context_scope"] == "open"
    assert second_data["related_summary_count"] == 0


def test_chat_returns_search_sources_when_search_hits(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_search(_: SearchService, __: str) -> list[SearchResult]:
        return [
            SearchResult(
                title="Example News",
                url="https://example.com/news",
                snippet="Example snippet.",
            )
        ]

    monkeypatch.setattr(SearchService, "search", fake_search)

    response = client.post(
        "/api/chat",
        json={"message": "today latest ai news"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["search_triggered"] is True
    assert data["search_used"] is True
    assert data["sources"][0]["title"] == "Example News"
    assert data["context_scope"] == "open"
