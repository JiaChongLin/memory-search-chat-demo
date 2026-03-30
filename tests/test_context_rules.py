from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.models import Base, ChatSession, Project, SessionSummary
from backend.app.services.context_resolver import ContextResolver
from backend.app.services.memory_service import MemoryService


def _build_db_session():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    db_path = temp_dir / f"context_rules_test_{uuid4().hex}.db"

    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return engine, session_local, db_path


def _create_project(db, name, access_mode="open", status="active"):
    project = Project(
        name=name,
        access_mode=access_mode,
        status=status,
    )
    db.add(project)
    db.flush()
    return project


def _create_session(
    db,
    session_id,
    project_id=None,
    status="active",
    is_private=False,
    summary=None,
):
    session = ChatSession(
        id=session_id,
        project_id=project_id,
        status=status,
        is_private=is_private,
    )
    db.add(session)
    db.flush()

    if summary is not None:
        db.add(SessionSummary(session_id=session_id, content=summary))

    return session


def _resolve_context(db, session_id: str):
    memory_service = MemoryService(db=db, short_window=2)
    return ContextResolver(db=db, memory_service=memory_service).resolve_context(
        session_id,
        allow_missing=False,
    )


def test_private_session_cannot_be_read_by_others() -> None:
    engine, session_local, db_path = _build_db_session()
    try:
        with session_local() as db:
            project = _create_project(db, "project-a", "open")
            _create_session(db, "current", project_id=project.id, summary="current-summary")
            _create_session(db, "private-one", project_id=project.id, is_private=True, summary="private-summary")
            _create_session(db, "shared-one", project_id=project.id, summary="shared-summary")
            db.commit()

            context = _resolve_context(db, "current")
            related_ids = {item.session_id for item in context.related_summaries}

            assert context.context_scope == "open"
            assert "shared-one" in related_ids
            assert "private-one" not in related_ids
    finally:
        engine.dispose()
        if db_path.exists():
            db_path.unlink()


def test_private_session_still_reads_other_allowed_history() -> None:
    engine, session_local, db_path = _build_db_session()
    try:
        with session_local() as db:
            open_project = _create_project(db, "open-project", "open")
            other_open_project = _create_project(db, "other-open", "open")
            _create_session(db, "current-private", project_id=open_project.id, is_private=True, summary="mine")
            _create_session(db, "same-project", project_id=open_project.id, summary="same-project-summary")
            _create_session(db, "other-project", project_id=other_open_project.id, summary="other-project-summary")
            _create_session(db, "no-project", summary="no-project-summary")
            db.commit()

            context = _resolve_context(db, "current-private")
            related_ids = {item.session_id for item in context.related_summaries}

            assert context.context_scope == "open"
            assert related_ids == {"same-project", "other-project", "no-project"}
    finally:
        engine.dispose()
        if db_path.exists():
            db_path.unlink()


def test_project_only_session_cannot_read_external_history() -> None:
    engine, session_local, db_path = _build_db_session()
    try:
        with session_local() as db:
            project_only_project = _create_project(db, "project-only", "project_only")
            open_project = _create_project(db, "open-project", "open")
            _create_session(db, "current", project_id=project_only_project.id, summary="current-summary")
            _create_session(db, "same-project", project_id=project_only_project.id, summary="same-project-summary")
            _create_session(db, "other-project", project_id=open_project.id, summary="other-project-summary")
            _create_session(db, "no-project", summary="no-project-summary")
            db.commit()

            context = _resolve_context(db, "current")
            related_ids = {item.session_id for item in context.related_summaries}

            assert context.context_scope == "project_only"
            assert related_ids == {"same-project"}
    finally:
        engine.dispose()
        if db_path.exists():
            db_path.unlink()


def test_open_project_session_can_read_external_open_and_shared_history() -> None:
    engine, session_local, db_path = _build_db_session()
    try:
        with session_local() as db:
            open_project = _create_project(db, "open-project", "open")
            project_only_project = _create_project(db, "project-only", "project_only")
            other_open_project = _create_project(db, "other-open", "open")
            _create_session(db, "current", project_id=open_project.id, summary="current-summary")
            _create_session(db, "same-project", project_id=open_project.id, summary="same-project-summary")
            _create_session(db, "other-open", project_id=other_open_project.id, summary="other-open-summary")
            _create_session(db, "other-project-only", project_id=project_only_project.id, summary="locked-summary")
            _create_session(db, "no-project-shared", summary="no-project-summary")
            db.commit()

            context = _resolve_context(db, "current")
            related_ids = {item.session_id for item in context.related_summaries}

            assert context.context_scope == "open"
            assert related_ids == {"same-project", "other-open", "no-project-shared"}
    finally:
        engine.dispose()
        if db_path.exists():
            db_path.unlink()


def test_project_only_session_is_not_visible_from_outside_project() -> None:
    engine, session_local, db_path = _build_db_session()
    try:
        with session_local() as db:
            open_project = _create_project(db, "open-project", "open")
            locked_project = _create_project(db, "locked-project", "project_only")
            _create_session(db, "current", project_id=open_project.id, summary="current-summary")
            _create_session(db, "inside-locked", project_id=locked_project.id, summary="locked-summary")
            _create_session(db, "shared-open", project_id=open_project.id, summary="open-summary")
            db.commit()

            context = _resolve_context(db, "current")
            related_ids = {item.session_id for item in context.related_summaries}

            assert "shared-open" in related_ids
            assert "inside-locked" not in related_ids
    finally:
        engine.dispose()
        if db_path.exists():
            db_path.unlink()


def test_no_project_shared_session_is_readable_from_open_context() -> None:
    engine, session_local, db_path = _build_db_session()
    try:
        with session_local() as db:
            open_project = _create_project(db, "open-project", "open")
            _create_session(db, "current", project_id=open_project.id, summary="current-summary")
            _create_session(db, "no-project-shared", summary="shared-summary")
            db.commit()

            context = _resolve_context(db, "current")
            related_ids = {item.session_id for item in context.related_summaries}

            assert "no-project-shared" in related_ids
    finally:
        engine.dispose()
        if db_path.exists():
            db_path.unlink()


def test_no_project_private_session_is_not_readable_from_other_sessions() -> None:
    engine, session_local, db_path = _build_db_session()
    try:
        with session_local() as db:
            _create_session(db, "current", summary="current-summary")
            _create_session(db, "no-project-private", is_private=True, summary="private-summary")
            _create_session(db, "no-project-shared", summary="shared-summary")
            db.commit()

            context = _resolve_context(db, "current")
            related_ids = {item.session_id for item in context.related_summaries}

            assert "no-project-shared" in related_ids
            assert "no-project-private" not in related_ids
    finally:
        engine.dispose()
        if db_path.exists():
            db_path.unlink()


def test_archived_sessions_do_not_enter_external_context() -> None:
    engine, session_local, db_path = _build_db_session()
    try:
        with session_local() as db:
            open_project = _create_project(db, "open-project", "open")
            _create_session(db, "current", project_id=open_project.id, summary="current-summary")
            _create_session(db, "active-one", project_id=open_project.id, summary="active-summary")
            _create_session(db, "archived-one", project_id=open_project.id, status="archived", summary="archived-summary")
            db.commit()

            context = _resolve_context(db, "current")
            related_ids = {item.session_id for item in context.related_summaries}
            context_text = context.context_summary or ""

            assert "active-one" in related_ids
            assert "archived-one" not in related_ids
            assert "archived-summary" not in context_text
    finally:
        engine.dispose()
        if db_path.exists():
            db_path.unlink()
