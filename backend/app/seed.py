import json
from pathlib import Path

from sqlalchemy import select

from .config import get_settings
from .db import SessionLocal, init_db
from .embeddings import EmbedderManager
from .models import FAQ


def resolve_seed_path() -> Path:
    settings = get_settings()
    default_path = Path(__file__).resolve().parent.parent.parent / "data" / "faqs.json"
    if not settings.seed_faq_path:
        return default_path

    configured = (Path(__file__).resolve().parent / settings.seed_faq_path).resolve()
    return configured if configured.exists() else default_path


def load_seed_dataset() -> list[dict[str, str]]:
    return json.loads(resolve_seed_path().read_text(encoding="utf-8"))


def seed_faqs() -> None:
    settings = get_settings()
    dataset = load_seed_dataset()
    embedder_manager = EmbedderManager(settings)
    embedder_manager.warmup()
    if not embedder_manager.state.ready:
        raise RuntimeError(embedder_manager.state.detail)

    init_db()
    with SessionLocal() as session:
        existing_questions = set(session.scalars(select(FAQ.question)).all())
        for entry in dataset:
            question = entry["question"].strip()
            if question in existing_questions:
                continue
            faq = FAQ(
                question=question,
                answer=entry["answer"].strip(),
                embedding=embedder_manager.embed(question),
                is_active=True,
            )
            session.add(faq)
        session.commit()


if __name__ == "__main__":
    seed_faqs()
