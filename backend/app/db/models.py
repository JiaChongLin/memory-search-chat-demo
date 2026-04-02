from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from backend.app.domain.constants import (
    PROJECT_ACCESS_OPEN,
    SESSION_SUMMARY_KIND_WORKING_MEMORY,
    STATUS_ACTIVE,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Human-facing project title. It can be a weak prompt signal via project_name,
    # but it is primarily a label for people navigating the workspace.
    name: Mapped[str] = mapped_column(String(255))
    # Human-readable project note for people browsing the workspace.
    # It is stored and returned to the UI, but intentionally excluded from model context.
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Project-level model instruction. This is the only project text field that enters chat model context.
    instruction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    access_mode: Mapped[str] = mapped_column(String(32), default=PROJECT_ACCESS_OPEN)
    status: Mapped[str] = mapped_column(String(20), default=STATUS_ACTIVE, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )

    sessions: Mapped[list["ChatSession"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    stable_facts: Mapped[list["ProjectStableFact"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), default=STATUS_ACTIVE, index=True)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    summary_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )

    project: Mapped[Optional["Project"]] = relationship(back_populates="sessions")
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    summaries: Mapped[list["SessionSummary"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    sources_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )

    session: Mapped["ChatSession"] = relationship(back_populates="messages")

    @property
    def sources(self) -> list[dict[str, Optional[str]]]:
        if not self.sources_json:
            return []

        try:
            payload = json.loads(self.sources_json)
        except (TypeError, ValueError):
            return []

        if not isinstance(payload, list):
            return []

        normalized: list[dict[str, Optional[str]]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue

            title = item.get("title")
            url = item.get("url")
            if not isinstance(title, str) or not isinstance(url, str):
                continue

            snippet = item.get("snippet")
            normalized.append(
                {
                    "title": title,
                    "url": url,
                    "snippet": snippet if isinstance(snippet, str) else None,
                }
            )

        return normalized


class SessionSummary(Base):
    __tablename__ = "session_summaries"
    __table_args__ = (
        UniqueConstraint("session_id", "kind", name="uq_session_summaries_session_kind"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        index=True,
    )
    kind: Mapped[str] = mapped_column(
        String(32),
        default=SESSION_SUMMARY_KIND_WORKING_MEMORY,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )

    session: Mapped["ChatSession"] = relationship(back_populates="summaries")


class ProjectStableFact(Base):
    __tablename__ = "project_stable_facts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default=STATUS_ACTIVE, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )

    project: Mapped["Project"] = relationship(back_populates="stable_facts")
