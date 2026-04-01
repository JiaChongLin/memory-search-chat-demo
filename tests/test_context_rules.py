from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.models import Base, ChatMessage, ChatSession, Project, SessionSummary
from backend.app.domain.constants import (
    SESSION_SUMMARY_KIND_SESSION_DIGEST,
    SESSION_SUMMARY_KIND_WORKING_MEMORY,
)
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
    working_memory=None,
    session_digest=None,
):
    session = ChatSession(
        id=session_id,
        project_id=project_id,
        status=status,
        is_private=is_private,
    )
    db.add(session)
    db.flush()

    if working_memory is not None:
        db.add(
            SessionSummary(
                session_id=session_id,
                kind=SESSION_SUMMARY_KIND_WORKING_MEMORY,
                content=working_memory,
            )
        )

    if session_digest is not None:
        db.add(
            SessionSummary(
                session_id=session_id,
                kind=SESSION_SUMMARY_KIND_SESSION_DIGEST,
                content=session_digest,
            )
        )

    return session


def _add_message(db, session_id: str, role: str, content: str):
    db.add(ChatMessage(session_id=session_id, role=role, content=content))


def _resolve_context(db, session_id: str):
    memory_service = MemoryService(db=db, short_window=2)
    return ContextResolver(db=db, memory_service=memory_service).resolve_context(
        session_id,
        allow_missing=False,
    )


def test_current_session_reads_working_memory_and_recent_messages() -> None:
    engine, session_local, db_path = _build_db_session()
    try:
        with session_local() as db:
            _create_session(
                db,
                "current",
                working_memory="User: old preference | Assistant: acknowledged",
                session_digest="Current state: full session digest",
            )
            _add_message(db, "current", "user", "recent question")
            _add_message(db, "current", "assistant", "recent answer")
            db.commit()

            context = _resolve_context(db, "current")

            assert context.working_memory == "User: old preference | Assistant: acknowledged"
            assert [item.content for item in context.recent_messages] == [
                "recent question",
                "recent answer",
            ]
    finally:
        engine.dispose()
        if db_path.exists():
            db_path.unlink()


def test_cross_session_reads_session_digest_not_working_memory() -> None:
    engine, session_local, db_path = _build_db_session()
    try:
        with session_local() as db:
            project = _create_project(db, "project-a", "open")
            _create_session(db, "current", project_id=project.id, session_digest="current digest")
            _create_session(
                db,
                "shared-one",
                project_id=project.id,
                working_memory="should stay private to that session",
                session_digest="shared digest for other sessions",
            )
            db.commit()

            context = _resolve_context(db, "current")
            related = {item.session_id: item.content for item in context.related_session_digests}

            assert related["shared-one"] == "shared digest for other sessions"
            assert "should stay private" not in related["shared-one"]
    finally:
        engine.dispose()
        if db_path.exists():
            db_path.unlink()


def test_private_session_cannot_be_read_by_others() -> None:
    engine, session_local, db_path = _build_db_session()
    try:
        with session_local() as db:
            project = _create_project(db, "project-a", "open")
            _create_session(db, "current", project_id=project.id, session_digest="current-summary")
            _create_session(
                db,
                "private-one",
                project_id=project.id,
                is_private=True,
                session_digest="private-summary",
            )
            _create_session(db, "shared-one", project_id=project.id, session_digest="shared-summary")
            db.commit()

            context = _resolve_context(db, "current")
            related_ids = {item.session_id for item in context.related_session_digests}

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
            _create_session(db, "current-private", project_id=open_project.id, is_private=True, session_digest="mine")
            _create_session(db, "same-project", project_id=open_project.id, session_digest="same-project-summary")
            _create_session(db, "other-project", project_id=other_open_project.id, session_digest="other-project-summary")
            _create_session(db, "no-project", session_digest="no-project-summary")
            db.commit()

            context = _resolve_context(db, "current-private")
            related_ids = {item.session_id for item in context.related_session_digests}

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
            _create_session(db, "current", project_id=project_only_project.id, session_digest="current-summary")
            _create_session(db, "same-project", project_id=project_only_project.id, session_digest="same-project-summary")
            _create_session(db, "other-project", project_id=open_project.id, session_digest="other-project-summary")
            _create_session(db, "no-project", session_digest="no-project-summary")
            db.commit()

            context = _resolve_context(db, "current")
            related_ids = {item.session_id for item in context.related_session_digests}

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
            _create_session(db, "current", project_id=open_project.id, session_digest="current-summary")
            _create_session(db, "same-project", project_id=open_project.id, session_digest="same-project-summary")
            _create_session(db, "other-open", project_id=other_open_project.id, session_digest="other-open-summary")
            _create_session(db, "other-project-only", project_id=project_only_project.id, session_digest="locked-summary")
            _create_session(db, "no-project-shared", session_digest="no-project-summary")
            db.commit()

            context = _resolve_context(db, "current")
            related_ids = {item.session_id for item in context.related_session_digests}

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
            _create_session(db, "current", project_id=open_project.id, session_digest="current-summary")
            _create_session(db, "inside-locked", project_id=locked_project.id, session_digest="locked-summary")
            _create_session(db, "shared-open", project_id=open_project.id, session_digest="open-summary")
            db.commit()

            context = _resolve_context(db, "current")
            related_ids = {item.session_id for item in context.related_session_digests}

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
            _create_session(db, "current", project_id=open_project.id, session_digest="current-summary")
            _create_session(db, "no-project-shared", session_digest="shared-summary")
            db.commit()

            context = _resolve_context(db, "current")
            related_ids = {item.session_id for item in context.related_session_digests}

            assert "no-project-shared" in related_ids
    finally:
        engine.dispose()
        if db_path.exists():
            db_path.unlink()


def test_no_project_private_session_is_not_readable_from_other_sessions() -> None:
    engine, session_local, db_path = _build_db_session()
    try:
        with session_local() as db:
            _create_session(db, "current", session_digest="current-summary")
            _create_session(db, "no-project-private", is_private=True, session_digest="private-summary")
            _create_session(db, "no-project-shared", session_digest="shared-summary")
            db.commit()

            context = _resolve_context(db, "current")
            related_ids = {item.session_id for item in context.related_session_digests}

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
            _create_session(db, "current", project_id=open_project.id, session_digest="current-summary")
            _create_session(db, "active-one", project_id=open_project.id, session_digest="active-summary")
            _create_session(db, "archived-one", project_id=open_project.id, status="archived", session_digest="archived-summary")
            db.commit()

            context = _resolve_context(db, "current")
            related_ids = {item.session_id for item in context.related_session_digests}
            related_text = " ".join(item.content for item in context.related_session_digests)

            assert "active-one" in related_ids
            assert "archived-one" not in related_ids
            assert "archived-summary" not in related_text
    finally:
        engine.dispose()
        if db_path.exists():
            db_path.unlink()


def test_is_private_toggle_takes_effect_immediately_for_context_reads() -> None:
    engine, session_local, db_path = _build_db_session()
    try:
        with session_local() as db:
            open_project = _create_project(db, "open-project", "open")
            _create_session(db, "current", project_id=open_project.id, session_digest="current-summary")
            toggled = _create_session(
                db,
                "toggle-me",
                project_id=open_project.id,
                is_private=False,
                session_digest="toggle-summary",
            )
            db.commit()

            initial_context = _resolve_context(db, "current")
            initial_ids = {item.session_id for item in initial_context.related_session_digests}
            assert "toggle-me" in initial_ids

            toggled.is_private = True
            db.commit()
            private_context = _resolve_context(db, "current")
            private_ids = {item.session_id for item in private_context.related_session_digests}
            assert "toggle-me" not in private_ids

            toggled.is_private = False
            db.commit()
            shared_again_context = _resolve_context(db, "current")
            shared_again_ids = {item.session_id for item in shared_again_context.related_session_digests}
            assert "toggle-me" in shared_again_ids
    finally:
        engine.dispose()
        if db_path.exists():
            db_path.unlink()
