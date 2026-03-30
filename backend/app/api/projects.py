from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import Project
from backend.app.db.session import get_db
from backend.app.schemas.chat import ErrorResponse
from backend.app.schemas.projects import ProjectCreateRequest, ProjectResponse


router = APIRouter()


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a project",
    responses={422: {"model": ErrorResponse}},
)
def create_project(
    payload: ProjectCreateRequest,
    db: Session = Depends(get_db),
) -> ProjectResponse:
    project = Project(**payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.get(
    "",
    response_model=list[ProjectResponse],
    summary="List projects",
)
def list_projects(
    include_archived: bool = Query(default=True),
    include_deleted: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[ProjectResponse]:
    stmt = select(Project).order_by(Project.updated_at.desc(), Project.id.desc())
    if not include_archived:
        stmt = stmt.where(Project.status != "archived")
    if not include_deleted:
        stmt = stmt.where(Project.status != "deleted")

    return [ProjectResponse.model_validate(project) for project in db.scalars(stmt)]


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get a project",
    responses={404: {"model": ErrorResponse}},
)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
) -> ProjectResponse:
    project = db.get(Project, project_id)
    if project is None or project.status == "deleted":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
    return ProjectResponse.model_validate(project)
