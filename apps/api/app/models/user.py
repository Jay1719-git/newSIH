from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_values
from app.models.enums import UserRole, UserStatus

if TYPE_CHECKING:
    from app.models.institution import Institution


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("institutions.id", ondelete="RESTRICT"), index=True
    )
    student_identity_reference_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("student_identity_references.id", ondelete="RESTRICT"),
        unique=True,
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=enum_values), nullable=False
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status", values_callable=enum_values),
        nullable=False,
        default=UserStatus.ACTIVE,
    )
    is_synthetic: Mapped[bool] = mapped_column(nullable=False, default=True, server_default="true")
    password_hash: Mapped[str | None] = mapped_column(String(256))

    institution: Mapped[Institution | None] = relationship(back_populates="users")
