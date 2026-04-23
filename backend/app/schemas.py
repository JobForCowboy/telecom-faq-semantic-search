from datetime import datetime
from typing import Any
from typing import Literal

from pydantic import BaseModel, Field


DecisionType = Literal["matched", "escalated", "out_of_domain"]
ChatStatus = Literal["matched", "clarification_required", "escalated", "out_of_domain"]
QuickReplyType = Literal["clarification", "intent_hypothesis", "followup", "fallback"]
MessageRole = Literal["user", "assistant"]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    embedding_backend: str
    model_name: str
    model_ready: bool
    detail: str | None = None


class ChatQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    conversation_id: str | None = Field(default=None, max_length=128)


class ChatResetRequest(BaseModel):
    conversation_id: str | None = Field(default=None, max_length=128)


class RetrievalMatchResponse(BaseModel):
    faq_id: int
    canonical_question: str
    matched_question: str
    score: float


class QuickReplyResponse(BaseModel):
    type: QuickReplyType
    label: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=240)


class ConversationMessageResponse(BaseModel):
    role: MessageRole
    text: str
    created_at: datetime
    decision_type: ChatStatus | None = None


class ChatQueryResponse(BaseModel):
    status: ChatStatus
    decision_type: DecisionType | None = None
    answer: str
    score: float | None = None
    matched_faq_id: int | None = None
    matched_question: str | None = None
    top_matches: list[RetrievalMatchResponse] = Field(default_factory=list)
    conversation_id: str = ""
    conversation_message_count: int = 0
    is_follow_up: bool = False
    clarification_question: str | None = None
    clarification_type: str | None = None
    quick_replies: list[QuickReplyResponse] = Field(default_factory=list)
    domain_score: float | None = None
    domain_reason: str | None = None
    ood_reason: str | None = None
    domain_signals: list[str] = Field(default_factory=list)
    domain_keyword_hits: list[str] = Field(default_factory=list)
    offtopic_rule_hit: str | None = None
    garbage_rule_hit: str | None = None
    soft_match_used: bool = False
    soft_match_reason: str | None = None
    top_score: float | None = None
    top2_score: float | None = None
    match_margin: float | None = None
    decision_path: list[str] = Field(default_factory=list)


class ChatResetResponse(BaseModel):
    conversation_id: str
    cleared: bool
    message_count: int = 0


class RetrievalDebugResponse(ChatQueryResponse):
    original_question: str
    normalized_question: str
    raw_query: str
    contextualized_query: str
    normalized_contextualized_query: str
    threshold: float
    match_threshold: float
    domain_threshold: float
    recent_messages: list[ConversationMessageResponse] = Field(default_factory=list)
    follow_up_detected: bool = False
    clarification_triggered: bool = False
    threshold_decision: ChatStatus


class FAQBase(BaseModel):
    canonical_question: str = Field(min_length=3, max_length=500)
    answer: str = Field(min_length=3, max_length=4000)
    variants: list[str] = Field(min_length=1, max_length=20)
    is_active: bool = True
    intent_tag: str | None = Field(default=None, min_length=2, max_length=64)
    intent_label: str | None = Field(default=None, min_length=2, max_length=120)


class FAQCreate(FAQBase):
    pass


class FAQUpdate(BaseModel):
    canonical_question: str | None = Field(default=None, min_length=3, max_length=500)
    answer: str | None = Field(default=None, min_length=3, max_length=4000)
    variants: list[str] | None = Field(default=None, min_length=1, max_length=20)
    is_active: bool | None = None
    intent_tag: str | None = Field(default=None, min_length=2, max_length=64)
    intent_label: str | None = Field(default=None, min_length=2, max_length=120)


class FAQResponse(FAQBase):
    id: int
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class EscalationResponse(BaseModel):
    id: int
    question_text: str
    normalized_question_text: str
    contextualized_question_text: str | None = None
    response_text: str
    score: float | None
    matched_faq_id: int | None
    matched_canonical_question: str | None
    conversation_id: str | None = None
    decision_type: ChatStatus | None = None
    domain_score: float | None = None
    domain_reason: str | None = None
    ood_reason: str | None = None
    soft_match_used: bool = False
    soft_match_reason: str | None = None
    top_score: float | None = None
    top2_score: float | None = None
    match_margin: float | None = None
    decision_path: list[str] = Field(default_factory=list)
    domain_signals: list[str] = Field(default_factory=list)
    domain_keyword_hits: list[str] = Field(default_factory=list)
    offtopic_rule_hit: str | None = None
    garbage_rule_hit: str | None = None
    retrieval_candidates: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


class OutOfDomainResponse(EscalationResponse):
    pass
