from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_values
from app.models.enums import AcademicYearStatus, ProgramStatus

if TYPE_CHECKING:
    from app.models.institution import Institution


class AcademicProgram(TimestampMixin, Base):
    __tablename__ = "academic_programs"
    __table_args__ = (
        UniqueConstraint("institution_id", "code", name="uq_program_institution_code"),
        UniqueConstraint("id", "institution_id", name="uq_program_id_institution"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("institutions.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[ProgramStatus] = mapped_column(
        Enum(ProgramStatus, name="program_status", values_callable=enum_values),
        nullable=False,
        default=ProgramStatus.ACTIVE,
    )

    institution: Mapped[Institution] = relationship(back_populates="programs")
    academic_years: Mapped[list[ProgramAcademicYear]] = relationship(back_populates="program")


class AcademicYear(TimestampMixin, Base):
    __tablename__ = "academic_years"
    __table_args__ = (
        CheckConstraint("ends_on > starts_on", name="valid_date_range"),
        UniqueConstraint("id", "code", name="uq_academic_year_id_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[AcademicYearStatus] = mapped_column(
        Enum(AcademicYearStatus, name="academic_year_status", values_callable=enum_values),
        nullable=False,
        default=AcademicYearStatus.PLANNED,
    )

    programs: Mapped[list[ProgramAcademicYear]] = relationship(back_populates="academic_year")


class ProgramAcademicYear(TimestampMixin, Base):
    __tablename__ = "program_academic_years"
    __table_args__ = (
        ForeignKeyConstraint(
            ["program_id", "institution_id"],
            ["academic_programs.id", "academic_programs.institution_id"],
            ondelete="RESTRICT",
            name="fk_program_year_program_tenant",
        ),
        UniqueConstraint("program_id", "academic_year_id", name="uq_program_academic_year"),
        UniqueConstraint("id", "institution_id", name="uq_program_year_id_institution"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    program_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("academic_years.id", ondelete="RESTRICT"), nullable=False
    )
    program: Mapped[AcademicProgram] = relationship(back_populates="academic_years")
    academic_year: Mapped[AcademicYear] = relationship(back_populates="programs")
    approved_intakes: Mapped[list[ApprovedIntake]] = relationship(back_populates="program_year")


class SeatCategory(TimestampMixin, Base):
    __tablename__ = "seat_categories"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True, server_default="true")

    approved_intakes: Mapped[list[ApprovedIntake]] = relationship(back_populates="seat_category")


class ApprovedIntake(TimestampMixin, Base):
    __tablename__ = "approved_intakes"
    __table_args__ = (
        CheckConstraint("approved_seats >= 0", name="nonnegative_approved_seats"),
        Index(
            "uq_approved_intake_program_year_category",
            "program_academic_year_id",
            "seat_category_id",
            unique=True,
        ),
        Index(
            "uq_approved_intake_total_program_year",
            "program_academic_year_id",
            unique=True,
            postgresql_where=text("seat_category_id IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program_academic_year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("program_academic_years.id", ondelete="RESTRICT"),
        nullable=False,
    )
    seat_category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("seat_categories.id", ondelete="RESTRICT")
    )
    approved_seats: Mapped[int] = mapped_column(Integer, nullable=False)

    program_year: Mapped[ProgramAcademicYear] = relationship(back_populates="approved_intakes")
    seat_category: Mapped[SeatCategory | None] = relationship(back_populates="approved_intakes")
