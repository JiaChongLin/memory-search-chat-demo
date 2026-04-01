from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.chat import ErrorResponse
from backend.app.schemas.projects import (
    ProjectCreateRequest,
    ProjectDeleteResponse,
    ProjectResponse,
    ProjectUpdateRequest,
    StableFactCreateRequest,
    StableFactDeleteResponse,
    StableFactResponse,
    StableFactUpdateRequest,
)
from backend.app.services.project_service import ProjectService
from backend.app.services.stable_fact_service import StableFactService


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


@router.get(
    "/{project_id}/stable-facts",
    response_model=list[StableFactResponse],
    summary="List project stable facts",
    responses={404: {"model": ErrorResponse}},
)
def list_project_stable_facts(
    project_id: int,
    include_archived: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[StableFactResponse]:
    facts = StableFactService(db).list_project_stable_facts(
        project_id,
        include_archived=include_archived,
    )
    return [StableFactResponse.model_validate(fact) for fact in facts]


@router.post(
    "/{project_id}/stable-facts",
    response_model=StableFactResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create project stable fact",
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def create_project_stable_fact(
    project_id: int,
    payload: StableFactCreateRequest,
    db: Session = Depends(get_db),
) -> StableFactResponse:
    fact = StableFactService(db).create_project_stable_fact(project_id, payload)
    return StableFactResponse.model_validate(fact)


@router.patch(
    "/{project_id}/stable-facts/{fact_id}",
    response_model=StableFactResponse,
    summary="Update project stable fact",
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def update_project_stable_fact(
    project_id: int,
    fact_id: int,
    payload: StableFactUpdateRequest,
    db: Session = Depends(get_db),
) -> StableFactResponse:
    fact = StableFactService(db).update_project_stable_fact(project_id, fact_id, payload)
    return StableFactResponse.model_validate(fact)


@router.delete(
    "/{project_id}/stable-facts/{fact_id}",
    response_model=StableFactDeleteResponse,
    summary="Delete project stable fact",
    responses={404: {"model": ErrorResponse}},
)
def delete_project_stable_fact(
    project_id: int,
    fact_id: int,
    db: Session = Depends(get_db),
) -> StableFactDeleteResponse:
    deleted_fact_id = StableFactService(db).delete_project_stable_fact(project_id, fact_id)
    return StableFactDeleteResponse(
        stable_fact_id=deleted_fact_id,
        message="Stable fact deleted.",
    )
