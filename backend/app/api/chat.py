from fastapi import APIRouter, Depends

from backend.app.schemas.chat import ChatRequest, ChatResponse
from backend.app.services.chat_service import ChatService, get_chat_service


router = APIRouter()


@router.post("", response_model=ChatResponse, summary="Handle a chat turn")
def create_chat_reply(
    payload: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    return chat_service.handle_chat(payload)
