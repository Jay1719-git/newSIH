from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_values
from app.models.enums import ReviewCaseStatus, ReviewCaseType

if TYPE_CHECKING:
    from app.models.identity import StudentIdentityReference
    from app.models.ingestion import ImportBatchRow


class ReviewCase(TimestampMixin, Base):
    __tablename__ = "review_cases"
    __table_args__ = (Index("ix_review_cases_institution_status", "institution_id", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("institutions.id", ondelete="RESTRICT"), nullable=False
    )
    import_row_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("import_batch_rows.id", ondelete="SET NULL")
    )
    identity_reference_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("student_identity_references.id", ondelete="RESTRICT"),
    )
    case_type: Mapped[ReviewCaseType] = mapped_column(
        Enum(ReviewCaseType, name="review_case_type", values_callable=enum_values), nullable=False
    )
    status: Mapped[ReviewCaseStatus] = mapped_column(
        Enum(ReviewCaseStatus, name="review_case_status", values_callable=enum_values),
        nullable=False,
        default=ReviewCaseStatus.OPEN,
    )
    resolution_action: Mapped[str | None] = mapped_column(String(48))
    resolution_notes: Mapped[str | None] = mapped_column(Text)
    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    import_row: Mapped[ImportBatchRow | None] = relationship()
    identity_reference: Mapped[StudentIdentityReference | None] = relationship()
