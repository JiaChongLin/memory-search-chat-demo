from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import get_settings
from backend.app.db.models import Base


settings = get_settings()

engine = create_engine(
    settings.database_url,
    # SQLite 在本地单进程开发时通常需要关闭线程检查。
    connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    # 供 FastAPI 依赖注入使用，请求结束后自动关闭会话。
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    # demo 阶段使用 create_all 即可完成本地建表。
    Base.metadata.create_all(bind=engine)
