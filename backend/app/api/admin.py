from fastapi import APIRouter, Depends, HTTPException, status

from .deps import get_admin_service, get_chat_service
from ..schemas import (
    ChatQueryRequest,
    EscalationResponse,
    FAQCreate,
    FAQResponse,
    FAQUpdate,
    RetrievalDebugResponse,
)
from ..services.admin import AdminService
from ..services.chat import ChatService


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/faqs", response_model=list[FAQResponse])
def list_faqs(service: AdminService = Depends(get_admin_service)) -> list[FAQResponse]:
    return service.list_faqs()


@router.post("/faqs", response_model=FAQResponse, status_code=status.HTTP_201_CREATED)
def create_faq(payload: FAQCreate, service: AdminService = Depends(get_admin_service)) -> FAQResponse:
    return service.create_faq(payload)


@router.put("/faqs/{faq_id}", response_model=FAQResponse)
def update_faq(
    faq_id: int,
    payload: FAQUpdate,
    service: AdminService = Depends(get_admin_service),
) -> FAQResponse:
    faq = service.update_faq(faq_id, payload)
    if faq is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FAQ not found")
    return faq


@router.delete("/faqs/{faq_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_faq(faq_id: int, service: AdminService = Depends(get_admin_service)) -> None:
    deleted = service.delete_faq(faq_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FAQ not found")


@router.get("/escalations", response_model=list[EscalationResponse])
def list_escalations(service: AdminService = Depends(get_admin_service)) -> list[EscalationResponse]:
    return service.list_escalations()


@router.post("/retrieval-debug", response_model=RetrievalDebugResponse)
def retrieval_debug(
    payload: ChatQueryRequest,
    service: ChatService = Depends(get_chat_service),
) -> RetrievalDebugResponse:
    return service.preview_question(payload.question, top_k=3)
