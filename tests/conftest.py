from pathlib import Path
import sys
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import backend.app.main as main_module
from backend.app.core.config import Settings
from backend.app.db.models import Base
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.services.chat_service import ChatService, get_chat_service
from backend.app.services.context_resolver import ContextResolver
from backend.app.services.llm_service import LLMService
from backend.app.services.memory_service import MemoryService
from backend.app.services.search_service import SearchService
from backend.app.services.session_service import SessionService


@pytest.fixture
def test_env(monkeypatch):
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
                session_service=SessionService(db=db),
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
        yield {
            "client": test_client,
            "session_local": testing_session_local,
            "db_path": db_path,
            "engine": engine,
        }

    app.dependency_overrides.clear()
    engine.dispose()
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def client(test_env):
    return test_env["client"]


@pytest.fixture
def session_local(test_env):
    return test_env["session_local"]
