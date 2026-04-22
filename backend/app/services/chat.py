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


def build_chat_response(
    candidates: list[MatchCandidate],
    threshold: float,
    fallback_message: str,
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
        )

    return ChatQueryResponse(
        status="matched",
        answer=candidate.answer,
        score=candidate.score,
        matched_faq_id=candidate.faq_id,
        matched_question=candidate.matched_question,
        top_matches=top_matches,
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
        original_question, normalized_question = self._prepare_question(question)
        candidates = self._find_top_matches(normalized_question)
        response = build_chat_response(
            candidates=candidates,
            threshold=self.settings.similarity_threshold,
            fallback_message=self.settings.fallback_message,
        )
        self._store_query(original_question, normalized_question, response)
        return response

    def preview_question(self, question: str, top_k: int = 3) -> RetrievalDebugResponse:
        original_question, normalized_question = self._prepare_question(question)
        candidates = self._find_top_matches(normalized_question, top_k=top_k)
        response = build_chat_response(
            candidates=candidates,
            threshold=self.settings.similarity_threshold,
            fallback_message=self.settings.fallback_message,
        )
        return RetrievalDebugResponse(
            original_question=original_question,
            normalized_question=normalized_question,
            threshold=self.settings.similarity_threshold,
            **response.model_dump(),
        )

    def _find_top_matches(self, question: str, top_k: int = 3) -> list[MatchCandidate]:
        try:
            vector = self.embedder_manager.embed(question)
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
                )
            )
            if len(candidates) == top_k:
                break
        return candidates

    def _prepare_question(self, question: str) -> tuple[str, str]:
        original_question = question.strip()
        return original_question, self.normalizer.normalize(original_question)

    def _store_query(
        self,
        question: str,
        normalized_question: str,
        response: ChatQueryResponse,
    ) -> None:
        record = UserQuery(
            question_text=question,
            normalized_question_text=normalized_question,
            response_text=response.answer,
            similarity_score=response.score,
            status=response.status,
            matched_faq_id=response.matched_faq_id,
        )
        self.session.add(record)
        self.session.commit()
