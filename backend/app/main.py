from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api import api_router
from backend.app.core.config import get_settings
from backend.app.db.session import init_db


settings = get_settings()

# 开发阶段先放开常见本地前端地址，方便直接联调。
DEV_CORS_ORIGINS = [
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    # 启动时自动建表，保证本地开发开箱即用。
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Minimal chat backend with conversation memory and search hooks.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=DEV_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_prefix)


def build_error_response(
    status_code: int,
    code: str,
    message: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
            }
        },
    )


@app.exception_handler(HTTPException)
async def handle_http_exception(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "请求处理失败。"
    return build_error_response(exc.status_code, "http_error", detail)


@app.exception_handler(RequestValidationError)
async def handle_validation_exception(
    _: Request,
    __: RequestValidationError,
) -> JSONResponse:
    return build_error_response(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "validation_error",
        "请求参数校验失败。",
    )


@app.exception_handler(Exception)
async def handle_unexpected_exception(_: Request, __: Exception) -> JSONResponse:
    return build_error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "internal_error",
        "服务器处理请求时发生异常。",
    )


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
