from sqlalchemy import Boolean, Float, ForeignKey, String, Text, UniqueConstraint, func
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
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    matched_faq_id: Mapped[int | None] = mapped_column(ForeignKey("faqs.id"), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    faq_entry: Mapped[FAQEntry | None] = relationship(back_populates="queries")
