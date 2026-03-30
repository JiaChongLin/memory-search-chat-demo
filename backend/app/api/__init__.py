from fastapi import APIRouter

from backend.app.api.chat import router as chat_router
from backend.app.api.projects import router as project_router
from backend.app.api.sessions import router as session_router


api_router = APIRouter()
api_router.include_router(chat_router, prefix="/chat", tags=["chat"])
api_router.include_router(project_router, prefix="/projects", tags=["projects"])
api_router.include_router(session_router, prefix="/sessions", tags=["sessions"])
