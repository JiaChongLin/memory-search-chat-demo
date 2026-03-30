from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from backend.app.db.models import Project, utcnow
from backend.app.domain.constants import (
    PROJECT_ACCESS_PROJECT_ONLY,
    STATUS_ACTIVE,
    STATUS_ARCHIVED,
    STATUS_DELETED,
)
from backend.app.schemas.projects import ProjectCreateRequest


class ProjectService:
    """Handle lightweight project management operations."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create_project(self, payload: ProjectCreateRequest) -> Project:
        if self._projects_table_has_legacy_required_columns():
            return self._create_project_with_legacy_columns(payload)

        project = Project(**payload.model_dump())
        self._db.add(project)
        self._db.commit()
        self._db.refresh(project)
        return project

    def list_projects(
        self,
        *,
        include_archived: bool = True,
        include_deleted: bool = False,
    ) -> list[Project]:
        stmt = select(Project).order_by(Project.updated_at.desc(), Project.id.desc())
        if not include_archived:
            stmt = stmt.where(Project.status != STATUS_ARCHIVED)
        if not include_deleted:
            stmt = stmt.where(Project.status != STATUS_DELETED)
        return list(self._db.scalars(stmt))

    def get_project(self, project_id: int) -> Project:
        project = self._db.get(Project, project_id)
        if project is None or project.status == STATUS_DELETED:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found.",
            )
        return project

    def _projects_table_has_legacy_required_columns(self) -> bool:
        bind = self._db.get_bind()
        inspector = inspect(bind)
        if not inspector.has_table("projects"):
            return False

        project_columns = {column["name"] for column in inspector.get_columns("projects")}
        return "scope_mode" in project_columns or "is_isolated" in project_columns

    def _create_project_with_legacy_columns(
        self,
        payload: ProjectCreateRequest,
    ) -> Project:
        bind = self._db.get_bind()
        inspector = inspect(bind)
        project_columns = {column["name"] for column in inspector.get_columns("projects")}

        now = utcnow()
        params = {
            "name": payload.name,
            "description": payload.description,
            "access_mode": payload.access_mode,
            "status": STATUS_ACTIVE,
            "created_at": now,
            "updated_at": now,
        }
        insert_columns = [
            "name",
            "description",
            "access_mode",
            "status",
            "created_at",
            "updated_at",
        ]

        if "scope_mode" in project_columns:
            params["scope_mode"] = (
                PROJECT_ACCESS_PROJECT_ONLY
                if payload.access_mode == PROJECT_ACCESS_PROJECT_ONLY
                else "global"
            )
            insert_columns.append("scope_mode")

        if "is_isolated" in project_columns:
            params["is_isolated"] = (
                1 if payload.access_mode == PROJECT_ACCESS_PROJECT_ONLY else 0
            )
            insert_columns.append("is_isolated")

        values_sql = ", ".join(f":{column}" for column in insert_columns)
        columns_sql = ", ".join(insert_columns)
        result = self._db.execute(
            text(f"INSERT INTO projects ({columns_sql}) VALUES ({values_sql})"),
            params,
        )
        self._db.commit()

        project_id = result.lastrowid
        if project_id is None:
            raise RuntimeError("Failed to create project.")
        return self.get_project(int(project_id))
