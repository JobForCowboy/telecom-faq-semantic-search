from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config import Settings
from ..embeddings import EmbedderManager, EmbedderUnavailableError
from ..models import FAQ, UserQuery
from ..schemas import EscalationResponse, FAQCreate, FAQResponse, FAQUpdate


class AdminService:
    def __init__(
        self,
        session: Session,
        embedder_manager: EmbedderManager,
        settings: Settings,
    ) -> None:
        self.session = session
        self.embedder_manager = embedder_manager
        self.settings = settings

    def list_faqs(self) -> list[FAQResponse]:
        faqs = self.session.scalars(select(FAQ).order_by(FAQ.updated_at.desc(), FAQ.id.desc())).all()
        return [FAQResponse.model_validate(faq) for faq in faqs]

    def create_faq(self, payload: FAQCreate) -> FAQResponse:
        embedding = self._embed(payload.question)
        faq = FAQ(
            question=payload.question.strip(),
            answer=payload.answer.strip(),
            is_active=payload.is_active,
            embedding=embedding,
        )
        self.session.add(faq)
        self.session.commit()
        self.session.refresh(faq)
        return FAQResponse.model_validate(faq)

    def update_faq(self, faq_id: int, payload: FAQUpdate) -> FAQResponse | None:
        faq = self.session.get(FAQ, faq_id)
        if faq is None:
            return None

        updates = payload.model_dump(exclude_unset=True)
        if "question" in updates and updates["question"] is not None:
            faq.question = updates["question"].strip()
            faq.embedding = self._embed(faq.question)
        if "answer" in updates and updates["answer"] is not None:
            faq.answer = updates["answer"].strip()
        if "is_active" in updates and updates["is_active"] is not None:
            faq.is_active = updates["is_active"]

        self.session.add(faq)
        self.session.commit()
        self.session.refresh(faq)
        return FAQResponse.model_validate(faq)

    def delete_faq(self, faq_id: int) -> bool:
        faq = self.session.get(FAQ, faq_id)
        if faq is None:
            return False
        self.session.execute(delete(FAQ).where(FAQ.id == faq_id))
        self.session.commit()
        return True

    def list_escalations(self) -> list[EscalationResponse]:
        escalations = self.session.scalars(
            select(UserQuery)
            .where(UserQuery.status == "escalated")
            .order_by(UserQuery.created_at.desc(), UserQuery.id.desc())
        ).all()
        return [EscalationResponse.model_validate(row) for row in escalations]

    def _embed(self, text: str) -> list[float]:
        try:
            return self.embedder_manager.embed(text)
        except EmbedderUnavailableError:
            raise
