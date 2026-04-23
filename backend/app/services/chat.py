from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..embeddings import EmbedderManager, EmbedderUnavailableError
from ..models import FAQEntry, FAQVariant, UserQuery
from ..normalization import get_text_normalizer
from ..schemas import ChatQueryResponse, RetrievalDebugResponse, RetrievalMatchResponse
from .decision_policy import DecisionPolicy


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
            decision_type="escalated",
            answer=fallback_message,
            score=candidate.score if candidate else None,
            matched_faq_id=candidate.faq_id if candidate else None,
            matched_question=candidate.matched_question if candidate else None,
            top_matches=top_matches,
            conversation_id=conversation_id,
            conversation_message_count=conversation_message_count,
            is_follow_up=is_follow_up,
            top_score=candidate.score if candidate else None,
        )

    return ChatQueryResponse(
        status="matched",
        decision_type="matched",
        answer=candidate.answer,
        score=candidate.score,
        matched_faq_id=candidate.faq_id,
        matched_question=candidate.matched_question,
        top_matches=top_matches,
        conversation_id=conversation_id,
        conversation_message_count=conversation_message_count,
        is_follow_up=is_follow_up,
        top_score=candidate.score,
        top2_score=candidates[1].score if len(candidates) > 1 else None,
        match_margin=(candidate.score - candidates[1].score) if len(candidates) > 1 else candidate.score,
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
        self.decision_policy = DecisionPolicy(settings)

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
        return self.decision_policy.decide(
            raw_query=original_question,
            normalized_query=normalized_question,
            candidates=candidates,
            conversation_id=conversation_id,
            conversation_message_count=conversation_message_count,
            is_follow_up=is_follow_up,
        ).response

    def preview_question(self, question: str, top_k: int = 3) -> RetrievalDebugResponse:
        original_question, normalized_question = self.prepare_question(question)
        response = self.answer_normalized_question(
            normalized_question,
            original_question=original_question,
            top_k=top_k,
        )
        top_score = response.top_score
        threshold_decision = "matched" if top_score is not None and top_score >= self.settings.effective_match_threshold else response.status
        return RetrievalDebugResponse(
            original_question=original_question,
            normalized_question=normalized_question,
            raw_query=original_question,
            contextualized_query=original_question,
            normalized_contextualized_query=normalized_question,
            threshold=self.settings.effective_match_threshold,
            match_threshold=self.settings.effective_match_threshold,
            domain_threshold=self.settings.domain_threshold,
            threshold_decision=threshold_decision,
            **response.model_dump(),
        )

    def find_top_matches(self, normalized_question: str, top_k: int = 3) -> list[MatchCandidate]:
        if not normalized_question.strip():
            return []
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
            decision_type=response.decision_type or response.status,
            domain_score=response.domain_score,
            domain_reason=response.domain_reason,
            ood_reason=response.ood_reason,
            soft_match_used=response.soft_match_used,
            soft_match_reason=response.soft_match_reason,
            top_score=response.top_score,
            top2_score=response.top2_score,
            match_margin=response.match_margin,
            decision_path=list(response.decision_path),
            domain_signals=list(response.domain_signals),
            domain_keyword_hits=list(response.domain_keyword_hits),
            offtopic_rule_hit=response.offtopic_rule_hit,
            garbage_rule_hit=response.garbage_rule_hit,
            retrieval_candidates=[item.model_dump() for item in response.top_matches],
            conversation_id=response.conversation_id or None,
            matched_faq_id=response.matched_faq_id,
        )
        self.session.add(record)
        self.session.commit()
