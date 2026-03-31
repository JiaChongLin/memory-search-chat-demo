from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import get_settings
from backend.app.db.models import Base
from backend.app.domain.constants import (
    PROJECT_ACCESS_OPEN,
    PROJECT_ACCESS_PROJECT_ONLY,
)


settings = get_settings()

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # type: ignore[no-untyped-def]
    del connection_record
    if not settings.database_url.startswith("sqlite"):
        return

    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate_sqlite_schema()


def _migrate_sqlite_schema() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    migration_statements: list[str] = []

    if inspector.has_table("projects"):
        project_columns = {column["name"] for column in inspector.get_columns("projects")}
        if "access_mode" not in project_columns:
            migration_statements.append(
                "ALTER TABLE projects ADD COLUMN access_mode VARCHAR(32) "
                f"NOT NULL DEFAULT '{PROJECT_ACCESS_OPEN}'"
            )

    if inspector.has_table("chat_sessions"):
        chat_session_columns = {
            column["name"] for column in inspector.get_columns("chat_sessions")
        }
        if "project_id" not in chat_session_columns:
            migration_statements.append(
                "ALTER TABLE chat_sessions ADD COLUMN project_id INTEGER"
            )
        if "status" not in chat_session_columns:
            migration_statements.append(
                "ALTER TABLE chat_sessions ADD COLUMN status VARCHAR(20) "
                "NOT NULL DEFAULT 'active'"
            )
        if "is_private" not in chat_session_columns:
            migration_statements.append(
                "ALTER TABLE chat_sessions ADD COLUMN is_private BOOLEAN "
                "NOT NULL DEFAULT 0"
            )
        if "last_message_at" not in chat_session_columns:
            migration_statements.append(
                "ALTER TABLE chat_sessions ADD COLUMN last_message_at DATETIME"
            )
        if "message_count" not in chat_session_columns:
            migration_statements.append(
                "ALTER TABLE chat_sessions ADD COLUMN message_count INTEGER "
                "NOT NULL DEFAULT 0"
            )
        if "summary_updated_at" not in chat_session_columns:
            migration_statements.append(
                "ALTER TABLE chat_sessions ADD COLUMN summary_updated_at DATETIME"
            )

    if migration_statements:
        with engine.begin() as connection:
            for statement in migration_statements:
                connection.execute(text(statement))

    inspector = inspect(engine)
    _backfill_project_access_mode(inspector)
    _backfill_session_metadata(inspector)


def _backfill_project_access_mode(inspector) -> None:  # type: ignore[no-untyped-def]
    if not inspector.has_table("projects"):
        return

    project_columns = {column["name"] for column in inspector.get_columns("projects")}
    if "access_mode" not in project_columns:
        return

    has_scope_mode = "scope_mode" in project_columns
    has_is_isolated = "is_isolated" in project_columns

    statements = [
        text(
            "UPDATE projects SET access_mode = :open_mode "
            "WHERE access_mode IS NULL OR TRIM(access_mode) = ''"
        )
    ]

    if has_scope_mode or has_is_isolated:
        conditions: list[str] = []
        if has_scope_mode:
            conditions.append("scope_mode = 'project_only'")
        if has_is_isolated:
            conditions.append("is_isolated = 1")

        if conditions:
            statements.append(
                text(
                    "UPDATE projects SET access_mode = :project_only_mode "
                    f"WHERE {' OR '.join(conditions)}"
                )
            )

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(
                statement,
                {
                    "open_mode": PROJECT_ACCESS_OPEN,
                    "project_only_mode": PROJECT_ACCESS_PROJECT_ONLY,
                },
            )


def _backfill_session_metadata(inspector) -> None:  # type: ignore[no-untyped-def]
    if not inspector.has_table("chat_sessions"):
        return

    session_columns = {column["name"] for column in inspector.get_columns("chat_sessions")}
    if "message_count" not in session_columns:
        return

    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE chat_sessions "
                "SET message_count = ("
                "  SELECT COUNT(*) FROM chat_messages "
                "  WHERE chat_messages.session_id = chat_sessions.id"
                ")"
            )
        )

        if "last_message_at" in session_columns and inspector.has_table("chat_messages"):
            connection.execute(
                text(
                    "UPDATE chat_sessions "
                    "SET last_message_at = ("
                    "  SELECT MAX(created_at) FROM chat_messages "
                    "  WHERE chat_messages.session_id = chat_sessions.id"
                    ")"
                )
            )

        if "summary_updated_at" in session_columns and inspector.has_table("session_summaries"):
            connection.execute(
                text(
                    "UPDATE chat_sessions "
                    "SET summary_updated_at = ("
                    "  SELECT updated_at FROM session_summaries "
                    "  WHERE session_summaries.session_id = chat_sessions.id"
                    ")"
                )
            )
