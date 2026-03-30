from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from backend.app.db.models import Project, utcnow
from backend.app.domain.constants import (
    PROJECT_ACCESS_PROJECT_ONLY,
    STATUS_ACTIVE,
)
from backend.app.schemas.projects import ProjectCreateRequest, ProjectUpdateRequest


class ProjectService:
    """Handle lightweight project management operations."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create_project(self, payload: ProjectCreateRequest) -> Project:
        normalized_name = self._normalize_name(payload.name)
        normalized_description = self._normalize_description(payload.description)
        normalized_payload = payload.model_copy(
            update={
                "name": normalized_name,
                "description": normalized_description,
            }
        )

        if self._projects_table_has_legacy_required_columns():
            return self._create_project_with_legacy_columns(normalized_payload)

        project = Project(**normalized_payload.model_dump(), status=STATUS_ACTIVE)
        self._db.add(project)
        self._db.commit()
        self._db.refresh(project)
        return project

    def list_projects(self) -> list[Project]:
        stmt = (
            select(Project)
            .where(Project.status == STATUS_ACTIVE)
            .order_by(Project.updated_at.desc(), Project.id.desc())
        )
        return list(self._db.scalars(stmt))

    def get_project(self, project_id: int) -> Project:
        project = self._db.get(Project, project_id)
        if project is None or project.status != STATUS_ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found.",
            )
        return project

    def update_project(self, project_id: int, payload: ProjectUpdateRequest) -> Project:
        project = self.get_project(project_id)
        changed = False

        if payload.name is not None:
            project.name = self._normalize_name(payload.name)
            changed = True

        if payload.description is not None:
            project.description = self._normalize_description(payload.description)
            changed = True

        if changed:
            project.updated_at = utcnow()
            self._db.add(project)
            self._db.commit()
            self._db.refresh(project)

        return project

    def delete_project(self, project_id: int) -> int:
        project = self.get_project(project_id)
        deleted_project_id = project.id
        self._db.delete(project)
        self._db.commit()
        return deleted_project_id

    def _normalize_name(self, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Project name cannot be empty.",
            )
        return normalized

    def _normalize_description(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

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

        params: dict[str, object] = {
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

        result = self._db.execute(
            text(
                f"INSERT INTO projects ({', '.join(insert_columns)}) "
                f"VALUES ({', '.join(f':{column}' for column in insert_columns)})"
            ),
            params,
        )
        self._db.commit()

        project_id = result.lastrowid
        if project_id is None:
            raise RuntimeError("Failed to create project.")
        return self.get_project(int(project_id))
