from fastapi import APIRouter, Depends

from .deps import get_chat_service
from ..schemas import ChatQueryRequest, ChatQueryResponse
from ..services.chat import ChatService


router = APIRouter(tags=["chat"])


@router.post("/chat/query", response_model=ChatQueryResponse)
def query_chat(payload: ChatQueryRequest, service: ChatService = Depends(get_chat_service)) -> ChatQueryResponse:
    return service.answer_question(payload.question)

