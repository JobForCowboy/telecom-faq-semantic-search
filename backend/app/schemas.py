from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    embedding_backend: str
    model_name: str
    model_ready: bool
    detail: str | None = None


class ChatQueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class ChatQueryResponse(BaseModel):
    status: Literal["matched", "fallback"]
    answer: str
    similarity_score: float | None = None
    matched_faq_id: int | None = None
    matched_question: str | None = None


class FAQBase(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    answer: str = Field(min_length=3, max_length=4000)
    is_active: bool = True


class FAQCreate(FAQBase):
    pass


class FAQUpdate(BaseModel):
    question: str | None = Field(default=None, min_length=3, max_length=500)
    answer: str | None = Field(default=None, min_length=3, max_length=4000)
    is_active: bool | None = None


class FAQResponse(FAQBase):
    id: int
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class EscalationResponse(BaseModel):
    id: int
    question_text: str
    response_text: str
    similarity_score: float | None
    created_at: datetime

    model_config = {"from_attributes": True}

