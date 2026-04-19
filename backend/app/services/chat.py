from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..embeddings import EmbedderManager, EmbedderUnavailableError
from ..models import FAQ, UserQuery
from ..schemas import ChatQueryResponse


@dataclass
class MatchCandidate:
    faq_id: int
    question: str
    answer: str
    score: float


def build_chat_response(
    candidate: MatchCandidate | None,
    threshold: float,
    fallback_message: str,
) -> ChatQueryResponse:
    if candidate is None or candidate.score < threshold:
        return ChatQueryResponse(
            status="fallback",
            answer=fallback_message,
            similarity_score=candidate.score if candidate else None,
            matched_faq_id=None,
            matched_question=None,
        )

    return ChatQueryResponse(
        status="matched",
        answer=candidate.answer,
        similarity_score=candidate.score,
        matched_faq_id=candidate.faq_id,
        matched_question=candidate.question,
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

    def answer_question(self, question: str) -> ChatQueryResponse:
        normalized_question = " ".join(question.split())
        candidate = self._find_best_match(normalized_question)
        response = build_chat_response(
            candidate=candidate,
            threshold=self.settings.similarity_threshold,
            fallback_message=self.settings.fallback_message,
        )
        self._store_query(normalized_question, response)
        return response

    def _find_best_match(self, question: str) -> MatchCandidate | None:
        try:
            vector = self.embedder_manager.embed(question)
        except EmbedderUnavailableError:
            raise

        distance_expr = FAQ.embedding.cosine_distance(vector)
        score_expr = (1 - distance_expr).label("score")
        statement = (
            select(FAQ, score_expr)
            .where(FAQ.is_active.is_(True))
            .order_by(distance_expr)
            .limit(1)
        )
        result = self.session.execute(statement).first()
        if result is None:
            return None

        faq, score = result
        return MatchCandidate(
            faq_id=faq.id,
            question=faq.question,
            answer=faq.answer,
            score=float(score),
        )

    def _store_query(self, question: str, response: ChatQueryResponse) -> None:
        record = UserQuery(
            question_text=question,
            response_text=response.answer,
            similarity_score=response.similarity_score,
            status="matched" if response.status == "matched" else "escalated",
            matched_faq_id=response.matched_faq_id,
        )
        self.session.add(record)
        self.session.commit()
