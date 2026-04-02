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
        422: {"model": ErrorResponse, "description": "\u8bf7\u6c42\u53c2\u6570\u6821\u9a8c\u5931\u8d25"},
        500: {"model": ErrorResponse, "description": "\u804a\u5929\u670d\u52a1\u6682\u65f6\u4e0d\u53ef\u7528"},
    },
)
def create_chat_reply(
    payload: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    try:
        return chat_service.handle_chat(payload)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("\u804a\u5929\u63a5\u53e3\u5904\u7406\u5931\u8d25")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="\u804a\u5929\u670d\u52a1\u6682\u65f6\u4e0d\u53ef\u7528\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002",
        ) from exc
