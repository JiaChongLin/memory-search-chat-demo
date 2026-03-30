from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import get_settings
from backend.app.db.models import Base


settings = get_settings()

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


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
    if not inspector.has_table("chat_sessions"):
        return

    chat_session_columns = {
        column["name"] for column in inspector.get_columns("chat_sessions")
    }
    migration_statements: list[str] = []

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

    if not migration_statements:
        return

    with engine.begin() as connection:
        for statement in migration_statements:
            connection.execute(text(statement))
