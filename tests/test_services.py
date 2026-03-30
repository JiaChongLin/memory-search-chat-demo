from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.config import Settings
from backend.app.db.models import Base
from backend.app.services.llm_service import LLMService
from backend.app.services.memory_service import MemoryService
from backend.app.services.search_service import DuckDuckGoHTMLParser, SearchResult


def build_settings(**overrides) -> Settings:
    defaults = dict(
        app_name="memory-search-chat-demo",
        app_env="test",
        api_prefix="/api",
        database_url="sqlite:///./test.db",
        llm_provider="dashscope",
        llm_api_key="",
        llm_model="qwen-plus",
        llm_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        llm_timeout_seconds=30,
        llm_fallback_enabled=True,
        memory_short_window=4,
        memory_summary_enabled=True,
        memory_summary_max_chars=600,
        search_enabled=True,
        search_provider="duckduckgo",
        search_base_url="https://html.duckduckgo.com/html/",
        search_timeout_seconds=15,
        search_max_results=5,
    )
    defaults.update(overrides)
    return Settings(**defaults)


def test_llm_service_falls_back_when_live_call_fails(monkeypatch) -> None:
    settings = build_settings(llm_api_key="demo-key")
    service = LLMService(settings=settings)

    def raise_error(_: list[dict[str, str]]) -> str:
        raise RuntimeError("network down")

    monkeypatch.setattr(service, "_call_dashscope", raise_error)

    reply = service.generate_reply(user_message="hello", history=[])

    assert reply.used_live_model is False
    assert reply.fallback_reason
    assert "provider_request_failed" in reply.fallback_reason
    assert "当前未能稳定调用在线模型" in reply.content


def test_memory_service_builds_summary_after_window() -> None:
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    db_path = temp_dir / f"memory_service_test_{uuid4().hex}.db"

    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    try:
        with session_local() as db:
            service = MemoryService(
                db=db,
                short_window=2,
                summary_enabled=True,
                summary_max_chars=200,
            )
            session_id = uuid4().hex

            service.append_turn(session_id, "我是小王", "你好，小王")
            service.append_turn(session_id, "我住在上海", "好的，我记住了")
            summary = service.append_turn(session_id, "我喜欢羽毛球", "收到")

            assert summary is not None
            assert "用户" in summary
    finally:
        engine.dispose()
        if db_path.exists():
            db_path.unlink()


def test_duckduckgo_parser_extracts_titles_urls_and_snippets() -> None:
    html = """
    <html>
      <body>
        <a class="result__a" href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fnews">
          Example News
        </a>
        <a class="result__snippet">Example snippet one.</a>
        <a class="result__a" href="https://example.org/post">Second Result</a>
        <div class="result__snippet">Another summary.</div>
      </body>
    </html>
    """

    parser = DuckDuckGoHTMLParser()
    parser.feed(html)
    parser.close()

    assert parser.results == [
        SearchResult(
            title="Example News",
            url="https://example.com/news",
            snippet="Example snippet one.",
        ),
        SearchResult(
            title="Second Result",
            url="https://example.org/post",
            snippet="Another summary.",
        ),
    ]


def test_project_service_can_create_project_against_legacy_projects_table() -> None:
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    db_path = temp_dir / f"legacy_project_service_test_{uuid4().hex}.db"

    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                scope_mode VARCHAR(32) NOT NULL,
                is_isolated BOOLEAN NOT NULL,
                status VARCHAR(20) NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                access_mode VARCHAR(32) NOT NULL DEFAULT 'open'
            )
            """
        )

    try:
        from backend.app.schemas.projects import ProjectCreateRequest
        from backend.app.services.project_service import ProjectService

        with session_local() as db:
            project = ProjectService(db).create_project(
                ProjectCreateRequest(name="legacy-compatible", access_mode="open")
            )

            assert project.id is not None
            assert project.name == "legacy-compatible"
            assert project.access_mode == "open"
    finally:
        engine.dispose()
        if db_path.exists():
            db_path.unlink()
