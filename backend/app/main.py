from fastapi import FastAPI

from backend.app.api import api_router
from backend.app.core.config import get_settings


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Minimal chat backend with conversation memory and search hooks.",
)
app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/", tags=["system"])
def read_root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "status": "ok",
        "docs": "/docs",
    }


@app.get("/health", tags=["system"])
def healthcheck() -> dict[str, str]:
    return {
        "status": "healthy",
        "environment": settings.app_env,
    }
