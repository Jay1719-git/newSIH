from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Enum, ForeignKey, Index, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_values
from app.models.enums import AuditEntityType

if TYPE_CHECKING:
    from app.models.institution import Institution
    from app.models.user import User


class AuditEvent(TimestampMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_events_institution_created", "institution_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("institutions.id", ondelete="RESTRICT")
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[AuditEntityType] = mapped_column(
        Enum(AuditEntityType, name="audit_entity_type", values_callable=enum_values),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    request_id: Mapped[str] = mapped_column(String(80), nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    previous_hash: Mapped[str | None] = mapped_column(String(64))
    event_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    institution: Mapped[Institution | None] = relationship()
    actor: Mapped[User | None] = relationship()
