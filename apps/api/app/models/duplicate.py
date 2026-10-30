from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class DuplicateCase(TimestampMixin, Base):
    __tablename__ = "duplicate_cases"
    __table_args__ = (
        CheckConstraint("record_a_id < record_b_id", name="canonical_record_pair"),
        Index("ix_duplicate_cases_a_status", "institution_a_id", "status"),
        Index("ix_duplicate_cases_b_status", "institution_b_id", "status"),
        Index("uq_duplicate_case_record_pair", "record_a_id", "record_b_id", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    record_a_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("import_batch_rows.id", ondelete="CASCADE"), nullable=False
    )
    record_b_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("import_batch_rows.id", ondelete="CASCADE"), nullable=False
    )
    institution_a_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("institutions.id", ondelete="RESTRICT"), nullable=False
    )
    institution_b_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("institutions.id", ondelete="RESTRICT"), nullable=False
    )
    match_type: Mapped[str] = mapped_column(String(48), nullable=False)
    confidence_band: Mapped[str] = mapped_column(String(16), nullable=False)
    reason_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="OPEN")
    outcome: Mapped[str | None] = mapped_column(String(32))
    decision_history: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    scan_count: Mapped[int] = mapped_column(nullable=False, default=1)
