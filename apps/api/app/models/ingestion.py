from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_values
from app.models.enums import FindingOutcome, ImportBatchStatus, ImportRowStatus

if TYPE_CHECKING:
    from app.models.identity import Enrolment, StudentIdentityReference
    from app.models.institution import Institution


class DataImportBatch(TimestampMixin, Base):
    __tablename__ = "data_import_batches"
    __table_args__ = (
        UniqueConstraint(
            "institution_id",
            "fingerprint_key_version",
            "content_fingerprint",
            name="uq_import_batch_tenant_fingerprint",
        ),
        CheckConstraint("total_rows >= 0", name="nonnegative_total_rows"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("institutions.id", ondelete="RESTRICT"), nullable=False
    )
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    fingerprint_key_version: Mapped[str] = mapped_column(String(40), nullable=False)
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[ImportBatchStatus] = mapped_column(
        Enum(ImportBatchStatus, name="import_batch_status", values_callable=enum_values),
        nullable=False,
        default=ImportBatchStatus.RECEIVED,
    )
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    institution: Mapped[Institution] = relationship(back_populates="import_batches")
    rows: Mapped[list[ImportBatchRow]] = relationship(
        back_populates="batch", cascade="all, delete-orphan", order_by="ImportBatchRow.row_number"
    )


class ImportBatchRow(TimestampMixin, Base):
    __tablename__ = "import_batch_rows"
    __table_args__ = (
        UniqueConstraint("batch_id", "row_number", name="uq_import_batch_row_number"),
        CheckConstraint("row_number > 0", name="positive_row_number"),
        Index("ix_import_rows_student_ref", "institution_id", "student_ref"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("data_import_batches.id", ondelete="CASCADE"), nullable=False
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("institutions.id", ondelete="RESTRICT"), nullable=False
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    student_ref: Mapped[str | None] = mapped_column(String(80))
    masked_apaar: Mapped[str | None] = mapped_column(String(16))
    identity_reference_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("student_identity_references.id", ondelete="RESTRICT"),
    )
    full_name: Mapped[str | None] = mapped_column(String(200))
    date_of_birth: Mapped[str | None] = mapped_column(String(10))
    program_academic_year_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("program_academic_years.id", ondelete="RESTRICT")
    )
    consent_granted: Mapped[bool | None] = mapped_column()
    admission_date: Mapped[date | None] = mapped_column(Date)
    seat_category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("seat_categories.id", ondelete="RESTRICT")
    )
    supernumerary_seat: Mapped[bool] = mapped_column(nullable=False, default=False)
    nri_status: Mapped[bool] = mapped_column(nullable=False, default=False)
    oci_status: Mapped[bool] = mapped_column(nullable=False, default=False)
    foreign_national_status: Mapped[bool] = mapped_column(nullable=False, default=False)
    admission_status: Mapped[str] = mapped_column(String(32), nullable=False, default="ADMITTED")
    row_status: Mapped[ImportRowStatus] = mapped_column(
        Enum(ImportRowStatus, name="import_row_status", values_callable=enum_values),
        nullable=False,
        default=ImportRowStatus.READY,
    )
    enrolment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("enrolments.id", ondelete="RESTRICT")
    )

    batch: Mapped[DataImportBatch] = relationship(back_populates="rows")
    identity_reference: Mapped[StudentIdentityReference | None] = relationship()
    enrolment: Mapped[Enrolment | None] = relationship(back_populates="import_rows")
    findings: Mapped[list[ValidationFinding]] = relationship(
        back_populates="import_row", cascade="all, delete-orphan"
    )


class ValidationFinding(TimestampMixin, Base):
    __tablename__ = "validation_findings"
    __table_args__ = (
        UniqueConstraint("import_row_id", "rule_code", name="uq_validation_finding_row_rule"),
        Index("ix_validation_findings_rule_outcome", "rule_code", "outcome"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    import_row_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("import_batch_rows.id", ondelete="CASCADE"), nullable=False
    )
    rule_code: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[FindingOutcome] = mapped_column(
        Enum(FindingOutcome, name="finding_outcome", values_callable=enum_values), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    affected_field: Mapped[str | None] = mapped_column(String(80))
    remediation: Mapped[str | None] = mapped_column(Text)

    import_row: Mapped[ImportBatchRow] = relationship(back_populates="findings")
