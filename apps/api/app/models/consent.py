from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_values
from app.models.enums import ConsentStatus

if TYPE_CHECKING:
    from app.models.identity import Enrolment


class ConsentRecord(TimestampMixin, Base):
    __tablename__ = "consent_records"
    __table_args__ = (Index("ix_consent_records_enrolment_status", "enrolment_id", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    enrolment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("enrolments.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[ConsentStatus] = mapped_column(
        Enum(ConsentStatus, name="consent_status", values_callable=enum_values), nullable=False
    )
    purpose: Mapped[str] = mapped_column(String(200), nullable=False)
    verifier_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    permitted_claims: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_reference: Mapped[str | None] = mapped_column(String(160))

    enrolment: Mapped[Enrolment] = relationship()
