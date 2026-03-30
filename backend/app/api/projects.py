from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.chat import ErrorResponse
from backend.app.schemas.projects import ProjectCreateRequest, ProjectResponse
from backend.app.services.project_service import ProjectService


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
    project = ProjectService(db).create_project(payload)
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
    projects = ProjectService(db).list_projects(
        include_archived=include_archived,
        include_deleted=include_deleted,
    )
    return [ProjectResponse.model_validate(project) for project in projects]


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
    project = ProjectService(db).get_project(project_id)
    return ProjectResponse.model_validate(project)
