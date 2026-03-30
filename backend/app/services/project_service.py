from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import Project
from backend.app.domain.constants import STATUS_ARCHIVED, STATUS_DELETED
from backend.app.schemas.projects import ProjectCreateRequest


class ProjectService:
    """Handle lightweight project management operations."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create_project(self, payload: ProjectCreateRequest) -> Project:
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
