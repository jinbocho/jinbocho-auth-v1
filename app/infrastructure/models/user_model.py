from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.session import Base

if TYPE_CHECKING:
    from app.infrastructure.models.library_model import LibraryModel
    from app.infrastructure.models.refresh_token_model import RefreshTokenModel


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    library_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("libraries.id", ondelete="CASCADE"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    annual_reading_goal: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str | None] = mapped_column(String(2), nullable=True)
    theme_name: Mapped[str | None] = mapped_column(String(20), nullable=True)
    theme_mode: Mapped[str | None] = mapped_column(String(10), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    password_set_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_privacy_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    consent_terms_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_selected_library_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("libraries.id", ondelete="SET NULL"), nullable=True
    )
    tour_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    guardian_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    birth_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # foreign_keys required: this table has two FKs to libraries.id
    # (library_id, last_selected_library_id), so the join is ambiguous
    # without pinning it explicitly.
    library: Mapped["LibraryModel"] = relationship(back_populates="users", foreign_keys=[library_id])
    # passive_deletes: trust the DB's ON DELETE CASCADE on refresh_tokens.user_id
    # instead of having the ORM null it out first (which violates NOT NULL).
    refresh_tokens: Mapped[list["RefreshTokenModel"]] = relationship(back_populates="user", passive_deletes=True)
