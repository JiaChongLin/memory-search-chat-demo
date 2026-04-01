from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import sessionmaker

from backend.app.core.config import Settings
from backend.app.db.models import Base, ChatSession, ProjectStableFact, SessionSummary
from backend.app.domain.constants import (
    SESSION_SUMMARY_KIND_SESSION_DIGEST,
    SESSION_SUMMARY_KIND_WORKING_MEMORY,
    STATUS_ARCHIVED,
)
from backend.app.schemas.projects import StableFactCreateRequest, StableFactUpdateRequest
from backend.app.services.context_resolver import RelatedSessionDigest
from backend.app.services.llm_service import LLMService
from backend.app.services.memory_service import MemoryService
from backend.app.services.search_service import DuckDuckGoHTMLParser, SearchResult
from backend.app.services.stable_fact_service import StableFactService


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


def test_llm_service_injects_project_context_stable_facts_and_memory_layers() -> None:
    service = LLMService(settings=build_settings())

    messages = service._build_messages(
        user_message="help me plan",
        history=[],
        stable_facts=["Default deliverables should be written in Chinese."],
        working_memory="User: old preference",
        related_session_digests=[],
        project_name="Roadmap Project",
        project_instruction="Always answer like a product lead.",
        search_results=[],
    )

    assert messages[1]["role"] == "system"
    assert "项目名称：Roadmap Project" in messages[1]["content"]
    assert "项目级 instruction：Always answer like a product lead." in messages[1]["content"]
    assert "stable facts" in messages[2]["content"]
    assert "Default deliverables should be written in Chinese." in messages[2]["content"]
    assert "working_memory" in messages[3]["content"]


def test_llm_service_renders_related_session_title_before_short_id() -> None:
    service = LLMService(settings=build_settings())

    messages = service._build_messages(
        user_message="同项目另一个会话叫什么？",
        history=[],
        stable_facts=[],
        working_memory=None,
        related_session_digests=[
            RelatedSessionDigest(
                session_id="91d4bfcc0f4c4200ae7a7b912ba01706",
                session_title="正确标题",
                project_id=1,
                content="Started with: User: hello",
                source_scope="project",
            )
        ],
        project_name="Shared Project",
        project_instruction=None,
        search_results=[],
    )

    related_context = messages[2]["content"]
    assert "《正确标题》(91d4bfcc)" in related_context
    assert "Started with: User: hello" in related_context


def test_llm_service_skips_project_context_and_stable_facts_for_unassigned_session() -> None:
    service = LLMService(settings=build_settings())

    messages = service._build_messages(
        user_message="help me plan",
        history=[],
        stable_facts=[],
        working_memory="User: old preference",
        related_session_digests=[],
        project_name=None,
        project_instruction=None,
        search_results=[],
    )

    assert len(messages) == 3
    assert "项目名称：" not in messages[1]["content"]
    assert "stable facts" not in messages[1]["content"]
    assert "working_memory" in messages[1]["content"]


def test_memory_service_builds_working_memory_after_window() -> None:
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

            service.append_turn(session_id, "my name is alice", "hello alice")
            service.append_turn(session_id, "i live in shanghai", "noted")
            snapshot = service.append_turn(session_id, "i like badminton", "got it")

            assert snapshot.working_memory is not None
            assert "User:" in snapshot.working_memory
            assert snapshot.session_digest is not None
    finally:
        engine.dispose()
        if db_path.exists():
            db_path.unlink()


def test_memory_service_builds_session_digest_from_full_session() -> None:
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    db_path = temp_dir / f"memory_digest_test_{uuid4().hex}.db"

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
                summary_max_chars=240,
            )
            session_id = uuid4().hex

            service.append_turn(session_id, "start a travel plan to tokyo", "let us start")
            service.append_turn(session_id, "budget is around 2000 dollars", "noted")
            snapshot = service.append_turn(session_id, "focus on food and museums", "sounds good")

            assert snapshot.session_digest is not None
            assert "start a travel plan to tokyo" in snapshot.session_digest
            assert "food and museums" in snapshot.session_digest
            assert snapshot.session_digest != snapshot.working_memory
    finally:
        engine.dispose()
        if db_path.exists():
            db_path.unlink()


def test_memory_service_updates_session_metadata_and_summary_timestamp() -> None:
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    db_path = temp_dir / f"memory_service_metadata_test_{uuid4().hex}.db"

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

            service.append_turn(session_id, "first", "reply")
            service.append_turn(session_id, "second", "reply")
            service.append_turn(session_id, "third", "reply")

            session = db.get(ChatSession, session_id)
            assert session is not None
            assert session.message_count == 6
            assert session.last_message_at is not None
            assert session.summary_updated_at is not None

            summary_kinds = {
                record.kind
                for record in db.scalars(
                    select(SessionSummary).where(SessionSummary.session_id == session_id)
                )
            }
            assert summary_kinds == {
                SESSION_SUMMARY_KIND_WORKING_MEMORY,
                SESSION_SUMMARY_KIND_SESSION_DIGEST,
            }
    finally:
        engine.dispose()
        if db_path.exists():
            db_path.unlink()


def test_session_summary_migration_handles_legacy_index_names(monkeypatch) -> None:
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    db_path = temp_dir / f"session_summary_migration_test_{uuid4().hex}.db"

    local_engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )

    with local_engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE chat_sessions (
                id VARCHAR(64) PRIMARY KEY
            )
            """
        )
        connection.exec_driver_sql(
            """
            CREATE TABLE session_summaries (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                session_id VARCHAR(64) NOT NULL,
                content TEXT NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY(session_id) REFERENCES chat_sessions (id) ON DELETE CASCADE
            )
            """
        )
        connection.exec_driver_sql(
            "CREATE INDEX ix_session_summaries_session_id ON session_summaries (session_id)"
        )
        connection.exec_driver_sql(
            "INSERT INTO chat_sessions (id) VALUES ('legacy-session')"
        )
        connection.exec_driver_sql(
            "INSERT INTO session_summaries (session_id, content, updated_at) VALUES ('legacy-session', 'legacy summary', '2026-04-01T00:00:00Z')"
        )

    try:
        from backend.app.db import session as session_module

        monkeypatch.setattr(session_module, "engine", local_engine)
        session_module._migrate_session_summaries_table()

        inspector = inspect(local_engine)
        columns = {column["name"] for column in inspector.get_columns("session_summaries")}
        indexes = {index["name"] for index in inspector.get_indexes("session_summaries")}

        assert "kind" in columns
        assert "ix_session_summaries_session_id" in indexes
        assert "ix_session_summaries_kind" in indexes

        with local_engine.connect() as connection:
            rows = connection.execute(
                select(
                    SessionSummary.session_id,
                    SessionSummary.kind,
                    SessionSummary.content,
                )
            ).all()

        assert rows == [
            ("legacy-session", SESSION_SUMMARY_KIND_WORKING_MEMORY, "legacy summary")
        ]
    finally:
        local_engine.dispose()
        if db_path.exists():
            db_path.unlink()


def test_stable_fact_service_can_archive_and_filter_active_facts() -> None:
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    db_path = temp_dir / f"stable_fact_service_test_{uuid4().hex}.db"

    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    try:
        from backend.app.db.models import Project

        with session_local() as db:
            project = Project(name="Stable Facts Project", access_mode="open", status="active")
            db.add(project)
            db.commit()
            db.refresh(project)

            service = StableFactService(db)
            fact = service.create_project_stable_fact(
                project.id,
                StableFactCreateRequest(content="Keep answers short and actionable."),
            )

            active_facts = service.list_project_stable_facts(project.id)
            assert [item.content for item in active_facts] == [fact.content]

            updated = service.update_project_stable_fact(
                project.id,
                fact.id,
                StableFactUpdateRequest(status=STATUS_ARCHIVED),
            )
            assert updated.status == STATUS_ARCHIVED

            assert service.list_project_stable_facts(project.id) == []
            archived = service.list_project_stable_facts(project.id, include_archived=True)
            assert len(archived) == 1
            assert archived[0].status == STATUS_ARCHIVED
            assert db.get(ProjectStableFact, fact.id) is not None
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
                instruction TEXT,
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
                ProjectCreateRequest(
                    name="legacy-compatible",
                    instruction="Use concise engineering language.",
                    access_mode="open",
                )
            )

            assert project.id is not None
            assert project.name == "legacy-compatible"
            assert project.instruction == "Use concise engineering language."
            assert project.access_mode == "open"
    finally:
        engine.dispose()
        if db_path.exists():
            db_path.unlink()
