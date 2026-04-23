from fastapi import APIRouter, Depends

from .deps import get_dialogue_chat_service
from ..schemas import ChatQueryRequest, ChatQueryResponse, ChatResetRequest, ChatResetResponse
from ..services.dialogue import DialogueChatService


router = APIRouter(tags=["chat"])


@router.post("/chat/query", response_model=ChatQueryResponse)
def query_chat(
    payload: ChatQueryRequest,
    service: DialogueChatService = Depends(get_dialogue_chat_service),
) -> ChatQueryResponse:
    return service.answer_question(payload.question, conversation_id=payload.conversation_id)


@router.post("/chat/reset", response_model=ChatResetResponse)
def reset_chat(
    payload: ChatResetRequest,
    service: DialogueChatService = Depends(get_dialogue_chat_service),
) -> ChatResetResponse:
    return service.reset_conversation(payload.conversation_id)
