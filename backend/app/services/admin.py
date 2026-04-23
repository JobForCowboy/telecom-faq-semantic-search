from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from ..config import Settings
from ..embeddings import EmbedderManager, EmbedderUnavailableError
from ..models import FAQEntry, FAQVariant, UserQuery
from ..normalization import get_text_normalizer, prepare_variants
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
        self.normalizer = get_text_normalizer()

    def list_faqs(self) -> list[FAQResponse]:
        faqs = self.session.scalars(
            select(FAQEntry)
            .options(selectinload(FAQEntry.variants))
            .order_by(FAQEntry.updated_at.desc(), FAQEntry.id.desc())
        ).all()
        return [self._serialize_faq(faq) for faq in faqs]

    def create_faq(self, payload: FAQCreate) -> FAQResponse:
        canonical_question = payload.canonical_question.strip()
        variants = self._build_variant_rows(canonical_question, payload.variants)
        faq = FAQEntry(
            canonical_question=canonical_question,
            answer=payload.answer.strip(),
            is_active=payload.is_active,
            intent_tag=self._normalize_optional_text(payload.intent_tag),
            intent_label=self._normalize_optional_text(payload.intent_label),
            embedding=self._embed(self.normalizer.normalize(canonical_question)),
        )
        faq.variants = variants
        self.session.add(faq)
        self.session.commit()
        self.session.refresh(faq)
        return self._serialize_faq(faq)

    def update_faq(self, faq_id: int, payload: FAQUpdate) -> FAQResponse | None:
        faq = self.session.scalar(
            select(FAQEntry).options(selectinload(FAQEntry.variants)).where(FAQEntry.id == faq_id)
        )
        if faq is None:
            return None

        updates = payload.model_dump(exclude_unset=True)
        canonical_question = faq.canonical_question
        if "canonical_question" in updates and updates["canonical_question"] is not None:
            canonical_question = updates["canonical_question"].strip()
            faq.canonical_question = canonical_question
            faq.embedding = self._embed(self.normalizer.normalize(canonical_question))
        if "answer" in updates and updates["answer"] is not None:
            faq.answer = updates["answer"].strip()
        if "is_active" in updates and updates["is_active"] is not None:
            faq.is_active = updates["is_active"]
        if "intent_tag" in updates:
            faq.intent_tag = self._normalize_optional_text(updates["intent_tag"])
        if "intent_label" in updates:
            faq.intent_label = self._normalize_optional_text(updates["intent_label"])
        if "variants" in updates and updates["variants"] is not None:
            self._replace_variants(faq, canonical_question, updates["variants"])
        elif "canonical_question" in updates and updates["canonical_question"] is not None:
            existing_variants = [variant.question for variant in faq.variants]
            self._replace_variants(faq, canonical_question, existing_variants)

        self.session.add(faq)
        self.session.commit()
        self.session.refresh(faq)
        return self._serialize_faq(faq)

    def delete_faq(self, faq_id: int) -> bool:
        faq = self.session.get(FAQEntry, faq_id)
        if faq is None:
            return False
        self.session.execute(delete(FAQEntry).where(FAQEntry.id == faq_id))
        self.session.commit()
        return True

    def list_escalations(self) -> list[EscalationResponse]:
        escalations = self.session.scalars(
            select(UserQuery)
            .options(selectinload(UserQuery.faq_entry))
            .where(UserQuery.status == "escalated")
            .order_by(UserQuery.created_at.desc(), UserQuery.id.desc())
        ).all()
        return [
            EscalationResponse(
                id=row.id,
                question_text=row.question_text,
                normalized_question_text=row.normalized_question_text,
                contextualized_question_text=row.contextualized_question_text,
                response_text=row.response_text,
                score=row.similarity_score,
                matched_faq_id=row.matched_faq_id,
                matched_canonical_question=row.faq_entry.canonical_question if row.faq_entry else None,
                conversation_id=row.conversation_id,
                decision_type=row.decision_type,
                created_at=row.created_at,
            )
            for row in escalations
        ]

    def _embed(self, text: str) -> list[float]:
        try:
            return self.embedder_manager.embed(text)
        except EmbedderUnavailableError:
            raise

    def _serialize_faq(self, faq: FAQEntry) -> FAQResponse:
        return FAQResponse(
            id=faq.id,
            canonical_question=faq.canonical_question,
            answer=faq.answer,
            variants=[variant.question for variant in faq.variants],
            is_active=faq.is_active,
            intent_tag=faq.intent_tag,
            intent_label=faq.intent_label,
            created_at=faq.created_at,
            updated_at=faq.updated_at,
        )

    def _normalize_optional_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def _build_variant_rows(self, canonical_question: str, variants: list[str]) -> list[FAQVariant]:
        prepared = prepare_variants(canonical_question, variants, self.normalizer)
        return [
            FAQVariant(
                question=variant.question,
                embedding=self._embed(variant.normalized_question),
            )
            for variant in prepared
        ]

    def _replace_variants(self, faq: FAQEntry, canonical_question: str, variants: list[str]) -> None:
        faq.variants.clear()
        self.session.flush()
        faq.variants = self._build_variant_rows(canonical_question, variants)
