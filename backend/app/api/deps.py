from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_session
from ..embeddings import EmbedderManager
from ..services.admin import AdminService
from ..services.chat import ChatService
from ..services.conversations import InMemoryConversationStore
from ..services.dialogue import DialogueChatService


def get_embedder_manager(request: Request) -> EmbedderManager:
    return request.app.state.embedder_manager


def get_chat_service(
    session: Session = Depends(get_session),
    embedder_manager: EmbedderManager = Depends(get_embedder_manager),
) -> ChatService:
    return ChatService(
        session=session,
        embedder_manager=embedder_manager,
        settings=get_settings(),
    )


def get_conversation_store(request: Request) -> InMemoryConversationStore:
    return request.app.state.conversation_store


def get_dialogue_chat_service(
    session: Session = Depends(get_session),
    embedder_manager: EmbedderManager = Depends(get_embedder_manager),
    conversation_store: InMemoryConversationStore = Depends(get_conversation_store),
) -> DialogueChatService:
    settings = get_settings()
    return DialogueChatService(
        chat_service=ChatService(
            session=session,
            embedder_manager=embedder_manager,
            settings=settings,
        ),
        conversation_store=conversation_store,
        settings=settings,
    )


def get_admin_service(
    session: Session = Depends(get_session),
    embedder_manager: EmbedderManager = Depends(get_embedder_manager),
) -> AdminService:
    return AdminService(
        session=session,
        embedder_manager=embedder_manager,
        settings=get_settings(),
    )


def raise_embedder_error(detail: str) -> None:
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)
