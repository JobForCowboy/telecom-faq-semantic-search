from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..embeddings import EmbedderManager, EmbedderUnavailableError
from ..models import FAQEntry, FAQVariant, UserQuery
from ..normalization import get_text_normalizer
from ..schemas import ChatQueryResponse, RetrievalDebugResponse, RetrievalMatchResponse


@dataclass
class MatchCandidate:
    faq_id: int
    canonical_question: str
    matched_question: str
    answer: str
    score: float
    intent_tag: str | None = None
    intent_label: str | None = None


def build_chat_response(
    candidates: list[MatchCandidate],
    threshold: float,
    fallback_message: str,
    *,
    conversation_id: str = "",
    conversation_message_count: int = 0,
    is_follow_up: bool = False,
) -> ChatQueryResponse:
    candidate = candidates[0] if candidates else None
    top_matches = [
        RetrievalMatchResponse(
            faq_id=item.faq_id,
            canonical_question=item.canonical_question,
            matched_question=item.matched_question,
            score=item.score,
        )
        for item in candidates
    ]
    if candidate is None or candidate.score < threshold:
        return ChatQueryResponse(
            status="escalated",
            answer=fallback_message,
            score=candidate.score if candidate else None,
            matched_faq_id=candidate.faq_id if candidate else None,
            matched_question=candidate.matched_question if candidate else None,
            top_matches=top_matches,
            conversation_id=conversation_id,
            conversation_message_count=conversation_message_count,
            is_follow_up=is_follow_up,
        )

    return ChatQueryResponse(
        status="matched",
        answer=candidate.answer,
        score=candidate.score,
        matched_faq_id=candidate.faq_id,
        matched_question=candidate.matched_question,
        top_matches=top_matches,
        conversation_id=conversation_id,
        conversation_message_count=conversation_message_count,
        is_follow_up=is_follow_up,
    )


class ChatService:
    def __init__(
        self,
        session: Session,
        embedder_manager: EmbedderManager,
        settings: Settings,
    ) -> None:
        self.session = session
        self.embedder_manager = embedder_manager
        self.settings = settings
        self.normalizer = get_text_normalizer()

    def answer_question(self, question: str) -> ChatQueryResponse:
        original_question, normalized_question = self.prepare_question(question)
        response = self.answer_normalized_question(
            normalized_question,
            original_question=original_question,
        )
        self.store_query(
            question=original_question,
            normalized_question=normalized_question,
            contextualized_question=original_question,
            response=response,
        )
        return response

    def answer_normalized_question(
        self,
        normalized_question: str,
        *,
        original_question: str,
        top_k: int = 3,
        conversation_id: str = "",
        conversation_message_count: int = 0,
        is_follow_up: bool = False,
    ) -> ChatQueryResponse:
        candidates = self.find_top_matches(normalized_question, top_k=top_k)
        return build_chat_response(
            candidates=candidates,
            threshold=self.settings.similarity_threshold,
            fallback_message=self.settings.fallback_message,
            conversation_id=conversation_id,
            conversation_message_count=conversation_message_count,
            is_follow_up=is_follow_up,
        )

    def preview_question(self, question: str, top_k: int = 3) -> RetrievalDebugResponse:
        original_question, normalized_question = self.prepare_question(question)
        response = self.answer_normalized_question(
            normalized_question,
            original_question=original_question,
            top_k=top_k,
        )
        return RetrievalDebugResponse(
            original_question=original_question,
            normalized_question=normalized_question,
            raw_query=original_question,
            contextualized_query=original_question,
            normalized_contextualized_query=normalized_question,
            threshold=self.settings.similarity_threshold,
            threshold_decision=response.status,
            **response.model_dump(),
        )

    def find_top_matches(self, normalized_question: str, top_k: int = 3) -> list[MatchCandidate]:
        try:
            vector = self.embedder_manager.embed(normalized_question)
        except EmbedderUnavailableError:
            raise

        distance_expr = FAQVariant.embedding.cosine_distance(vector)
        score_expr = (1 - distance_expr).label("score")
        statement = (
            select(FAQVariant, FAQEntry, score_expr)
            .join(FAQEntry, FAQVariant.faq_entry_id == FAQEntry.id)
            .where(FAQEntry.is_active.is_(True))
            .order_by(distance_expr)
            .limit(max(top_k * 5, top_k))
        )
        rows = self.session.execute(statement).all()
        candidates: list[MatchCandidate] = []
        seen_faq_ids: set[int] = set()
        for variant, faq_entry, score in rows:
            if faq_entry.id in seen_faq_ids:
                continue
            seen_faq_ids.add(faq_entry.id)
            candidates.append(
                MatchCandidate(
                    faq_id=faq_entry.id,
                    canonical_question=faq_entry.canonical_question,
                    matched_question=variant.question,
                    answer=faq_entry.answer,
                    score=float(score),
                    intent_tag=faq_entry.intent_tag,
                    intent_label=faq_entry.intent_label,
                )
            )
            if len(candidates) == top_k:
                break
        return candidates

    def prepare_question(self, question: str) -> tuple[str, str]:
        original_question = question.strip()
        return original_question, self.normalizer.normalize(original_question)

    def store_query(
        self,
        *,
        question: str,
        normalized_question: str,
        contextualized_question: str | None,
        response: ChatQueryResponse,
    ) -> None:
        record = UserQuery(
            question_text=question,
            normalized_question_text=normalized_question,
            contextualized_question_text=contextualized_question,
            response_text=response.answer,
            similarity_score=response.score,
            status=response.status,
            decision_type=response.status,
            conversation_id=response.conversation_id or None,
            matched_faq_id=response.matched_faq_id,
        )
        self.session.add(record)
        self.session.commit()
