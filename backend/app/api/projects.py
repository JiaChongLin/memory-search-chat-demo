from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.chat import ErrorResponse
from backend.app.schemas.projects import (
    ProjectCreateRequest,
    ProjectDeleteResponse,
    ProjectResponse,
    ProjectUpdateRequest,
)
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
    db: Session = Depends(get_db),
) -> list[ProjectResponse]:
    projects = ProjectService(db).list_projects()
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


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update a project",
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def update_project(
    project_id: int,
    payload: ProjectUpdateRequest,
    db: Session = Depends(get_db),
) -> ProjectResponse:
    project = ProjectService(db).update_project(project_id, payload)
    return ProjectResponse.model_validate(project)


@router.delete(
    "/{project_id}",
    response_model=ProjectDeleteResponse,
    summary="Delete a project",
    responses={404: {"model": ErrorResponse}},
)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
) -> ProjectDeleteResponse:
    deleted_project_id = ProjectService(db).delete_project(project_id)
    return ProjectDeleteResponse(
        project_id=deleted_project_id,
        message="Project deleted.",
    )
