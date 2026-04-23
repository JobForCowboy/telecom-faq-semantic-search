import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .config import get_settings
from .db import SessionLocal, init_db
from .embeddings import EmbedderManager
from .models import FAQEntry, FAQVariant
from .normalization import get_text_normalizer, kb_dir, prepare_variants


def resolve_seed_path() -> Path:
    settings = get_settings()
    default_path = kb_dir() / "faqs.json"
    if not settings.seed_faq_path:
        return default_path

    configured = (Path(__file__).resolve().parent / settings.seed_faq_path).resolve()
    return configured if configured.exists() else default_path


def load_seed_dataset() -> list[dict[str, object]]:
    return json.loads(resolve_seed_path().read_text(encoding="utf-8"))


def seed_faqs() -> None:
    settings = get_settings()
    embedder_manager = EmbedderManager(settings)
    embedder_manager.warmup()
    if not embedder_manager.state.ready:
        raise RuntimeError(embedder_manager.state.detail)

    init_db()
    with SessionLocal() as session:
        bootstrap_faqs(session, embedder_manager)


def bootstrap_faqs(
    session: Session,
    embedder_manager: EmbedderManager,
    dataset: list[dict[str, object]] | None = None,
) -> None:
    dataset = dataset or load_seed_dataset()
    normalizer = get_text_normalizer()
    existing_entries = {
        faq.canonical_question: faq
        for faq in session.scalars(
            select(FAQEntry).options(selectinload(FAQEntry.variants))
        ).all()
    }

    # Backfill variant rows for legacy databases that only had canonical FAQ rows.
    for faq in existing_entries.values():
        if faq.variants:
            continue
        faq.variants = build_variant_rows(faq.canonical_question, [], embedder_manager)
        session.add(faq)

    for raw_entry in dataset:
        entry = normalize_seed_entry(raw_entry)
        canonical_question = entry["canonical_question"]
        existing = existing_entries.get(canonical_question)

        if existing is None:
            faq = FAQEntry(
                canonical_question=canonical_question,
                answer=entry["answer"],
                is_active=entry["is_active"],
                intent_tag=entry["intent_tag"],
                intent_label=entry["intent_label"],
                embedding=embedder_manager.embed(normalizer.normalize(canonical_question)),
            )
            faq.variants = build_variant_rows(canonical_question, entry["variants"], embedder_manager)
        else:
            faq = existing
            faq.answer = entry["answer"]
            faq.is_active = entry["is_active"]
            faq.intent_tag = entry["intent_tag"]
            faq.intent_label = entry["intent_label"]
            faq.embedding = embedder_manager.embed(normalizer.normalize(canonical_question))
            replace_variants(session, faq, canonical_question, entry["variants"], embedder_manager)
        session.add(faq)

    session.commit()


def build_variant_rows(
    canonical_question: str,
    variants: list[str],
    embedder_manager: EmbedderManager,
) -> list[FAQVariant]:
    normalizer = get_text_normalizer()
    prepared = prepare_variants(canonical_question, variants, normalizer)
    return [
        FAQVariant(
            question=variant.question,
            embedding=embedder_manager.embed(variant.normalized_question),
        )
        for variant in prepared
    ]


def replace_variants(
    session: Session,
    faq: FAQEntry,
    canonical_question: str,
    variants: list[str],
    embedder_manager: EmbedderManager,
) -> None:
    faq.variants.clear()
    session.flush()
    faq.variants = build_variant_rows(canonical_question, variants, embedder_manager)


def normalize_seed_entry(entry: dict[str, object]) -> dict[str, object]:
    canonical_question = str(entry.get("canonical_question") or entry.get("question") or "").strip()
    answer = str(entry.get("answer") or "").strip()
    intent_tag = str(entry.get("intent_tag") or "").strip() or None
    intent_label = str(entry.get("intent_label") or "").strip() or None
    raw_variants = entry.get("variants")
    variants = raw_variants if isinstance(raw_variants, list) else []
    prepared_variants = prepare_variants(canonical_question, [str(item) for item in variants])

    if not canonical_question or not answer or not prepared_variants:
        raise ValueError(f"Invalid FAQ seed entry: {entry}")

    return {
        "canonical_question": canonical_question,
        "answer": answer,
        "variants": [variant.question for variant in prepared_variants],
        "is_active": bool(entry.get("is_active", True)),
        "intent_tag": intent_tag,
        "intent_label": intent_label,
    }


if __name__ == "__main__":
    seed_faqs()
