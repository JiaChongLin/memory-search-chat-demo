from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import Project, ProjectStableFact, utcnow
from backend.app.domain.constants import STATUS_ACTIVE, STATUS_ARCHIVED
from backend.app.schemas.projects import StableFactCreateRequest, StableFactUpdateRequest


class StableFactService:
    """Manage project-level stable facts / saved memories."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def list_project_stable_facts(
        self,
        project_id: int,
        *,
        include_archived: bool = False,
    ) -> list[ProjectStableFact]:
        self._get_project(project_id)

        stmt = select(ProjectStableFact).where(ProjectStableFact.project_id == project_id)
        if not include_archived:
            stmt = stmt.where(ProjectStableFact.status == STATUS_ACTIVE)

        stmt = stmt.order_by(ProjectStableFact.updated_at.desc(), ProjectStableFact.id.desc())
        return list(self._db.scalars(stmt))

    def create_project_stable_fact(
        self,
        project_id: int,
        payload: StableFactCreateRequest,
    ) -> ProjectStableFact:
        project = self._get_project(project_id)
        fact = ProjectStableFact(
            project_id=project.id,
            content=self._normalize_content(payload.content),
            status=STATUS_ACTIVE,
        )
        self._db.add(fact)
        self._db.commit()
        self._db.refresh(fact)
        return fact

    def update_project_stable_fact(
        self,
        project_id: int,
        fact_id: int,
        payload: StableFactUpdateRequest,
    ) -> ProjectStableFact:
        fact = self._get_project_stable_fact(project_id, fact_id)
        changes = payload.model_dump(exclude_unset=True)
        changed = False

        if "content" in changes:
            fact.content = self._normalize_content(payload.content or "")
            changed = True

        if "status" in changes and payload.status is not None:
            fact.status = self._normalize_status(payload.status)
            changed = True

        if changed:
            fact.updated_at = utcnow()
            self._db.add(fact)
            self._db.commit()
            self._db.refresh(fact)

        return fact

    def delete_project_stable_fact(self, project_id: int, fact_id: int) -> int:
        fact = self._get_project_stable_fact(project_id, fact_id)
        deleted_fact_id = fact.id
        self._db.delete(fact)
        self._db.commit()
        return deleted_fact_id

    def _get_project(self, project_id: int) -> Project:
        project = self._db.get(Project, project_id)
        if project is None or project.status != STATUS_ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found.",
            )
        return project

    def _get_project_stable_fact(self, project_id: int, fact_id: int) -> ProjectStableFact:
        self._get_project(project_id)
        stmt = select(ProjectStableFact).where(
            ProjectStableFact.id == fact_id,
            ProjectStableFact.project_id == project_id,
        )
        fact = self._db.scalars(stmt).one_or_none()
        if fact is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Stable fact not found.",
            )
        return fact

    def _normalize_content(self, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Stable fact content cannot be empty.",
            )
        return normalized

    def _normalize_status(self, value: str) -> str:
        if value not in {STATUS_ACTIVE, STATUS_ARCHIVED}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Stable fact status is invalid.",
            )
        return value
