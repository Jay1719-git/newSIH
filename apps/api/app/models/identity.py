from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_values
from app.models.enums import EnrolmentStatus

if TYPE_CHECKING:
    from app.models.ingestion import ImportBatchRow


class StudentIdentityReference(TimestampMixin, Base):
    __tablename__ = "student_identity_references"
    __table_args__ = (
        CheckConstraint("length(hmac_digest) = 64", name="hmac_digest_sha256_length"),
        CheckConstraint(
            "masked_apaar ~ '^\\*{4}-\\*{4}-[0-9]{4}$'",
            name="masked_apaar_format",
        ),
        Index("uq_identity_hmac_key_digest", "key_version", "hmac_digest", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key_version: Mapped[str] = mapped_column(String(40), nullable=False)
    normalization_version: Mapped[str] = mapped_column(
        String(40), nullable=False, default="identity-norm-v1", server_default="legacy-v0"
    )
    hmac_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    masked_apaar: Mapped[str] = mapped_column(String(16), nullable=False)

    enrolments: Mapped[list[Enrolment]] = relationship(back_populates="identity_reference")


class Enrolment(TimestampMixin, Base):
    __tablename__ = "enrolments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["program_academic_year_id", "institution_id"],
            ["program_academic_years.id", "program_academic_years.institution_id"],
            ondelete="RESTRICT",
            name="fk_enrolments_program_year_tenant",
        ),
        Index("ix_enrolments_identity_reference_id", "identity_reference_id"),
        Index("ix_enrolments_program_year_status", "program_academic_year_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("institutions.id", ondelete="RESTRICT"), nullable=False
    )
    identity_reference_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("student_identity_references.id", ondelete="RESTRICT"),
    )
    program_academic_year_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    seat_category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("seat_categories.id", ondelete="RESTRICT")
    )
    student_ref: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[EnrolmentStatus] = mapped_column(
        Enum(EnrolmentStatus, name="enrolment_status", values_callable=enum_values),
        nullable=False,
        default=EnrolmentStatus.PENDING_REVIEW,
    )

    identity_reference: Mapped[StudentIdentityReference] = relationship(back_populates="enrolments")
    import_rows: Mapped[list[ImportBatchRow]] = relationship(back_populates="enrolment")
