from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings
from .models import Base


settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE IF EXISTS user_queries "
                "ADD COLUMN IF NOT EXISTS normalized_question_text TEXT NOT NULL DEFAULT ''"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE IF EXISTS user_queries "
                "ADD COLUMN IF NOT EXISTS contextualized_question_text TEXT"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE IF EXISTS user_queries "
                "ADD COLUMN IF NOT EXISTS decision_type VARCHAR(32)"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE IF EXISTS user_queries "
                "ADD COLUMN IF NOT EXISTS domain_score DOUBLE PRECISION"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE IF EXISTS user_queries "
                "ADD COLUMN IF NOT EXISTS domain_reason TEXT"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE IF EXISTS user_queries "
                "ADD COLUMN IF NOT EXISTS ood_reason TEXT"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE IF EXISTS user_queries "
                "ADD COLUMN IF NOT EXISTS soft_match_used BOOLEAN NOT NULL DEFAULT FALSE"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE IF EXISTS user_queries "
                "ADD COLUMN IF NOT EXISTS soft_match_reason TEXT"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE IF EXISTS user_queries "
                "ADD COLUMN IF NOT EXISTS top_score DOUBLE PRECISION"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE IF EXISTS user_queries "
                "ADD COLUMN IF NOT EXISTS top2_score DOUBLE PRECISION"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE IF EXISTS user_queries "
                "ADD COLUMN IF NOT EXISTS match_margin DOUBLE PRECISION"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE IF EXISTS user_queries "
                "ADD COLUMN IF NOT EXISTS decision_path JSONB"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE IF EXISTS user_queries "
                "ADD COLUMN IF NOT EXISTS domain_signals JSONB"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE IF EXISTS user_queries "
                "ADD COLUMN IF NOT EXISTS domain_keyword_hits JSONB"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE IF EXISTS user_queries "
                "ADD COLUMN IF NOT EXISTS offtopic_rule_hit VARCHAR(64)"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE IF EXISTS user_queries "
                "ADD COLUMN IF NOT EXISTS garbage_rule_hit VARCHAR(64)"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE IF EXISTS user_queries "
                "ADD COLUMN IF NOT EXISTS retrieval_candidates JSONB"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE IF EXISTS user_queries "
                "ADD COLUMN IF NOT EXISTS conversation_id VARCHAR(128)"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE IF EXISTS faqs "
                "ADD COLUMN IF NOT EXISTS intent_tag VARCHAR(64)"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE IF EXISTS faqs "
                "ADD COLUMN IF NOT EXISTS intent_label VARCHAR(120)"
            )
        )
