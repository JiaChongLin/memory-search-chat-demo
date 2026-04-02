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
from backend.app.services.llm_service import (
    MAX_RELATED_DIGESTS,
    MAX_SEARCH_RESULTS,
    MAX_STABLE_FACTS,
    LLMService,
)
from backend.app.services.memory_service import MemoryMessage, MemoryService
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
def test_llm_service_injects_project_context_stable_facts_and_memory_layers() -> None:
    service = LLMService(settings=build_settings())

    messages = service._build_messages(
        user_message="help me plan",
        history=[MemoryMessage(role="assistant", content="recent reply")],
        stable_facts=["Default deliverables should be written in Chinese."],
        working_memory="Current topic: Tokyo travel plan\nConfirmed info:\n- Budget around 2000 USD",
        related_session_digests=[
            RelatedSessionDigest(
                session_id="91d4bfcc0f4c4200ae7a7b912ba01706",
                session_title="Correct title",
                project_id=1,
                content="Session topic: hello",
                source_scope="project",
            )
        ],
        project_name="Roadmap Project",
        project_instruction="Always answer like a product lead.",
        search_results=[
            SearchResult(
                title="Tokyo planning reference",
                url="https://example.com/tokyo",
                snippet="A short search snippet.",
            )
        ],
    )

    assert messages[1]["role"] == "system"
    assert "Roadmap Project" in messages[1]["content"]
    assert "Always answer like a product lead." in messages[1]["content"]
    assert "stable facts" in messages[2]["content"]
    assert "Default deliverables should be written in Chinese." in messages[2]["content"]
    assert "working_memory" in messages[3]["content"]
    assert "Tokyo travel plan" in messages[3]["content"]
    assert "session_digest" in messages[4]["content"]
    assert "Correct title" in messages[4]["content"]
    assert "Tokyo planning reference" in messages[5]["content"]
    assert messages[6] == {"role": "assistant", "content": "recent reply"}
    assert messages[7] == {"role": "user", "content": "help me plan"}


    assert "项目级 instruction：Always answer like a product lead." in messages[1]["content"]
def test_llm_service_applies_context_budgets_without_losing_layers() -> None:
    service = LLMService(settings=build_settings())

    messages = service._build_messages(
        user_message="Need a concise answer.",
        history=[],
        stable_facts=[f"fact {index}: " + ("x" * 260) for index in range(1, 10)],
        working_memory="Current topic: long context budget test\nRuntime state: " + ("y" * 2200),
        related_session_digests=[
            RelatedSessionDigest(
                session_id=f"session-{index:02d}-abcdef0123456789",
                session_title=f"Session {index}",
                project_id=1,
                content=("digest " + str(index) + " ") + ("z" * 500),
                source_scope="project",
            )
            for index in range(1, 8)
        ],
        project_name="Budget Test Project",
        project_instruction="Use concise bullets and keep output grounded.",
        search_results=[
            SearchResult(
                title=f"Result {index}",
                url=f"https://example.com/{index}",
                snippet="snippet " + ("s" * 400),
            )
            for index in range(1, 7)
        ],
    )

    assert len(messages) == 7
    assert "Budget Test Project" in messages[1]["content"]
    assert "stable facts" in messages[2]["content"]
    assert "working_memory" in messages[3]["content"]
    assert "session_digest" in messages[4]["content"]
    assert "https://example.com/1" in messages[5]["content"]
    assert messages[2]["content"].count("\n") <= MAX_STABLE_FACTS
    assert f"{MAX_STABLE_FACTS + 1}." not in messages[2]["content"]
    assert f"Result {MAX_SEARCH_RESULTS + 1}" not in messages[5]["content"]
    assert f"Session {MAX_RELATED_DIGESTS + 1}" not in messages[4]["content"]
    assert len(messages[3]["content"]) < 1500




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
                content="会话主题：hello",
                source_scope="project",
            )
        ],
        project_name="Shared Project",
        project_instruction=None,
        search_results=[],
    )

    related_context = messages[2]["content"]
    assert "《正确标题》(91d4bfcc)" in related_context
    assert "会话主题：hello" in related_context


def test_llm_service_uses_instruction_not_description_for_project_prompt() -> None:
    service = LLMService(settings=build_settings())

    project_context = service._render_project_context(
        project_name="Roadmap Project",
        project_instruction="Always answer like a product lead.",
    )

    assert project_context is not None
    assert "Roadmap Project" in project_context
    assert "Always answer like a product lead." in project_context
    assert "description" not in project_context.casefold()


def test_llm_service_skips_project_context_and_stable_facts_for_unassigned_session() -> None:
    service = LLMService(settings=build_settings())

    messages = service._build_messages(
        user_message="help me plan",
        history=[],
        stable_facts=[],
        working_memory="当前讨论主题：old preference",
        related_session_digests=[],
        project_name=None,
        project_instruction=None,
        search_results=[],
    )

    assert len(messages) == 3
    assert "项目名称：" not in messages[1]["content"]
    assert "stable facts" not in messages[1]["content"]
    assert "当前讨论主题：old preference" in messages[1]["content"]


def test_memory_service_builds_structured_working_memory_after_window() -> None:
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
                summary_max_chars=520,
            )
            session_id = uuid4().hex

            service.append_turn(session_id, "Plan a Tokyo trip", "Okay, we will outline the trip goals.")
            service.append_turn(session_id, "Keep the budget under 2000 USD", "Noted, budget stays under 2000 USD.")
            service.append_turn(session_id, "What visa details are still missing?", "provider_request_failed while checking current visa rules.")
            snapshot = service.append_turn(session_id, "Prioritize food and museums", "Understood, I will focus on food and museums.")

            assert snapshot.working_memory is not None
            assert "\u5f53\u524d\u8ba8\u8bba\u4e3b\u9898\uff1a" in snapshot.working_memory
            assert "\u5df2\u786e\u8ba4\u4fe1\u606f\uff1a" in snapshot.working_memory
            assert "\u8fd0\u884c\u65f6\u72b6\u6001\uff1a" in snapshot.working_memory
            assert "\u5f85\u7ee7\u7eed\u5173\u6ce8\uff1a" in snapshot.working_memory
            assert "Keep the budget under 2000 USD" in snapshot.working_memory
            assert "What visa details are still missing?" in snapshot.working_memory
            assert "\u8fdb\u5165\u6700\u8fd1\u7a97\u53e3\u524d\uff0c\u52a9\u624b\u5df2\u63a8\u8fdb\u5230\uff1a" in snapshot.working_memory
            assert "User:" not in snapshot.working_memory
    finally:
        engine.dispose()
        if db_path.exists():
            db_path.unlink()

def test_memory_service_builds_structured_session_digest_from_full_session() -> None:
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
                summary_max_chars=620,
            )
            session_id = uuid4().hex

            service.append_turn(session_id, "Start a Tokyo travel plan", "Okay, we will sketch a three-day route.")
            service.append_turn(session_id, "Keep the budget under 2000 USD", "Noted, budget stays under 2000 USD.")
            service.append_turn(session_id, "What visa details are still missing?", "provider_request_failed while checking current visa rules.")
            snapshot = service.append_turn(session_id, "Prioritize food and museums", "Current recommendation is to keep Ueno and Asakusa in the core route.")

            assert snapshot.session_digest is not None
            assert "\u4f1a\u8bdd\u4e3b\u9898\uff1a" in snapshot.session_digest
            assert "\u5173\u952e\u7ed3\u8bba\uff1a" in snapshot.session_digest
            assert "\u5f53\u524d\u72b6\u6001\uff1a" in snapshot.session_digest
            assert "\u672a\u51b3\u95ee\u9898\uff1a" in snapshot.session_digest
            assert "Start a Tokyo travel plan" in snapshot.session_digest
            assert "Keep the budget under 2000 USD" in snapshot.session_digest
            assert "\u6700\u65b0\u7528\u6237\u5173\u6ce8\uff1aPrioritize food and museums" in snapshot.session_digest
            assert "Ueno and Asakusa" in snapshot.session_digest
            assert "What visa details are still missing?" in snapshot.session_digest
            assert snapshot.session_digest != snapshot.working_memory
    finally:
        engine.dispose()
        if db_path.exists():
            db_path.unlink()

def test_session_digest_reuses_previous_digest_sections_when_merging() -> None:
    service = MemoryService(db=None, short_window=2, summary_enabled=True, summary_max_chars=400)  # type: ignore[arg-type]

    previous_digest = (
        "会话主题：东京旅行计划\n"
        "关键结论：\n"
        "- 预算控制在 2000 美元内\n"
        "当前状态：\n"
        "- 最新助手回复：先整理交通方案\n"
    )
    messages = [
        MemoryMessage(role="user", content="接下来重点关注美食和博物馆"),
        MemoryMessage(role="assistant", content="好的，当前先补充上野和浅草的候选点位。"),
    ]

    digest = service.build_session_digest(
        session_id="demo",
        messages=messages,
        previous_digest=previous_digest,
    )

    assert digest is not None
    assert "预算控制在 2000 美元内" in digest
    assert "接下来重点关注美食和博物馆" in digest
    assert "上野和浅草" in digest


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
                summary_max_chars=220,
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
