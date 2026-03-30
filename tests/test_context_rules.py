from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.models import Base, ChatSession, Project, SessionSummary
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


def _create_project(db, name, scope_mode, is_isolated=False, status="active"):
    project = Project(
        name=name,
        scope_mode=scope_mode,
        is_isolated=is_isolated,
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


def test_private_session_is_not_readable_from_same_project() -> None:
    engine, session_local, db_path = _build_db_session()
    try:
        with session_local() as db:
            project = _create_project(db, "project-a", "project_only")
            _create_session(db, "current", project_id=project.id, summary="current-summary")
            _create_session(
                db,
                "private-one",
                project_id=project.id,
                is_private=True,
                summary="private-summary",
            )
            _create_session(
                db,
                "public-one",
                project_id=project.id,
                summary="public-summary",
            )
            db.commit()

            context = MemoryService(db=db, short_window=2).resolve_context("current")
            related_ids = {item.session_id for item in context.related_summaries}

            assert context.context_scope == "project_only"
            assert "public-one" in related_ids
            assert "private-one" not in related_ids
    finally:
        engine.dispose()
        if db_path.exists():
            db_path.unlink()


def test_isolated_project_content_is_hidden_from_external_global_session() -> None:
    engine, session_local, db_path = _build_db_session()
    try:
        with session_local() as db:
            isolated_project = _create_project(
                db,
                "isolated",
                "project_only",
                is_isolated=True,
            )
            global_project = _create_project(db, "global", "global")
            _create_session(
                db,
                "inside-isolated",
                project_id=isolated_project.id,
                summary="isolated-summary",
            )
            _create_session(
                db,
                "global-current",
                project_id=global_project.id,
                summary="global-current-summary",
            )
            _create_session(
                db,
                "public-external",
                summary="public-external-summary",
            )
            db.commit()

            context = MemoryService(db=db, short_window=2).resolve_context("global-current")
            related_ids = {item.session_id for item in context.related_summaries}

            assert context.context_scope == "global"
            assert "public-external" in related_ids
            assert "inside-isolated" not in related_ids
    finally:
        engine.dispose()
        if db_path.exists():
            db_path.unlink()


def test_project_only_reads_only_project_visible_history() -> None:
    engine, session_local, db_path = _build_db_session()
    try:
        with session_local() as db:
            project_one = _create_project(db, "project-one", "project_only")
            project_two = _create_project(db, "project-two", "project_only")
            _create_session(db, "current", project_id=project_one.id, summary="current-summary")
            _create_session(db, "same-project", project_id=project_one.id, summary="same-project-summary")
            _create_session(db, "other-project", project_id=project_two.id, summary="other-project-summary")
            _create_session(db, "no-project", summary="no-project-summary")
            db.commit()

            context = MemoryService(db=db, short_window=2).resolve_context("current")
            related_ids = {item.session_id for item in context.related_summaries}

            assert context.context_scope == "project_only"
            assert related_ids == {"same-project"}
    finally:
        engine.dispose()
        if db_path.exists():
            db_path.unlink()


def test_global_reads_only_allowed_history() -> None:
    engine, session_local, db_path = _build_db_session()
    try:
        with session_local() as db:
            current_project = _create_project(db, "current-project", "global")
            other_project = _create_project(db, "other-project", "project_only")
            isolated_project = _create_project(
                db,
                "isolated-project",
                "project_only",
                is_isolated=True,
            )

            _create_session(db, "current", project_id=current_project.id, summary="current-summary")
            _create_session(db, "visible-project", project_id=other_project.id, summary="visible-project-summary")
            _create_session(db, "visible-global", summary="visible-global-summary")
            _create_session(
                db,
                "private-session",
                project_id=other_project.id,
                is_private=True,
                summary="private-summary",
            )
            _create_session(
                db,
                "deleted-session",
                project_id=other_project.id,
                status="deleted",
                summary="deleted-summary",
            )
            _create_session(
                db,
                "archived-session",
                project_id=other_project.id,
                status="archived",
                summary="archived-summary",
            )
            _create_session(
                db,
                "isolated-session",
                project_id=isolated_project.id,
                summary="isolated-summary",
            )
            db.commit()

            context = MemoryService(db=db, short_window=2).resolve_context("current")
            related_ids = {item.session_id for item in context.related_summaries}

            assert context.context_scope == "global"
            assert related_ids == {"visible-project", "visible-global"}
    finally:
        engine.dispose()
        if db_path.exists():
            db_path.unlink()


def test_deleted_session_never_enters_context() -> None:
    engine, session_local, db_path = _build_db_session()
    try:
        with session_local() as db:
            project = _create_project(db, "global-project", "global")
            _create_session(db, "current", project_id=project.id, summary="current-summary")
            _create_session(
                db,
                "deleted-one",
                project_id=project.id,
                status="deleted",
                summary="deleted-summary",
            )
            db.commit()

            context = MemoryService(db=db, short_window=2).resolve_context("current")
            related_ids = {item.session_id for item in context.related_summaries}

            assert "deleted-one" not in related_ids
            assert "deleted-summary" not in (context.context_summary or "")
    finally:
        engine.dispose()
        if db_path.exists():
            db_path.unlink()
