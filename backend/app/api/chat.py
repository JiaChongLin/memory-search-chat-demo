import logging

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.schemas.chat import ChatRequest, ChatResponse, ErrorResponse
from backend.app.services.chat_service import ChatService, get_chat_service


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "",
    response_model=ChatResponse,
    summary="Handle a chat turn",
    responses={
        422: {"model": ErrorResponse, "description": "请求参数校验失败"},
        500: {"model": ErrorResponse, "description": "聊天服务暂时不可用"},
    },
)
def create_chat_reply(
    payload: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    # 路由层只负责接收请求和委托给 service。
    try:
        return chat_service.handle_chat(payload)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("聊天接口处理失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="聊天服务暂时不可用，请稍后重试。",
        ) from exc
