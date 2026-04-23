from sqlalchemy import JSON, Boolean, Float, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql.sqltypes import DateTime
from pgvector.sqlalchemy import Vector

from .config import get_settings


settings = get_settings()


class Base(DeclarativeBase):
    pass


class FAQEntry(Base):
    __tablename__ = "faqs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    canonical_question: Mapped[str] = mapped_column("question", Text, unique=True, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    intent_tag: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    intent_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Keep the legacy embedding column populated for compatibility with existing databases.
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dim), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    variants: Mapped[list["FAQVariant"]] = relationship(
        back_populates="faq_entry",
        cascade="all, delete-orphan",
        order_by="FAQVariant.id",
    )
    queries: Mapped[list["UserQuery"]] = relationship(back_populates="faq_entry")


class FAQVariant(Base):
    __tablename__ = "faq_variants"
    __table_args__ = (UniqueConstraint("faq_entry_id", "question", name="uq_faq_variants_entry_question"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    faq_entry_id: Mapped[int] = mapped_column(ForeignKey("faqs.id", ondelete="CASCADE"), nullable=False, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dim), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    faq_entry: Mapped["FAQEntry"] = relationship(back_populates="variants")


class UserQuery(Base):
    __tablename__ = "user_queries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_question_text: Mapped[str] = mapped_column(Text, nullable=False)
    contextualized_question_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    decision_type: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    domain_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    domain_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ood_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    soft_match_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    soft_match_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    top_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    top2_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    match_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    decision_path: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    domain_signals: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    domain_keyword_hits: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    offtopic_rule_hit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    garbage_rule_hit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retrieval_candidates: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    matched_faq_id: Mapped[int | None] = mapped_column(ForeignKey("faqs.id"), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    faq_entry: Mapped[FAQEntry | None] = relationship(back_populates="queries")
