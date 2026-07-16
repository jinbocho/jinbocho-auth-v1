from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.session import Base

if TYPE_CHECKING:
    from app.infrastructure.models.user_model import UserModel


class LibraryModel(Base):
    __tablename__ = "libraries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    kids_mode_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # passive_deletes: trust the DB's ON DELETE CASCADE on users.library_id
    # instead of having the ORM null it out first (which violates NOT NULL).
    # foreign_keys required: users has two FKs to libraries.id (library_id,
    # last_selected_library_id) so the join is ambiguous without pinning it.
    users: Mapped[list["UserModel"]] = relationship(
        back_populates="library", foreign_keys="UserModel.library_id", passive_deletes=True
    )
