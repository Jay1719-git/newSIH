from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_values
from app.models.enums import InstitutionStatus

if TYPE_CHECKING:
    from app.models.academics import AcademicProgram
    from app.models.ingestion import DataImportBatch
    from app.models.user import User


class Institution(TimestampMixin, Base):
    __tablename__ = "institutions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    aicte_code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    tier: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[InstitutionStatus] = mapped_column(
        Enum(InstitutionStatus, name="institution_status", values_callable=enum_values),
        nullable=False,
        default=InstitutionStatus.ACTIVE,
    )
    is_synthetic: Mapped[bool] = mapped_column(nullable=False, default=True, server_default="true")

    users: Mapped[list[User]] = relationship(back_populates="institution")
    programs: Mapped[list[AcademicProgram]] = relationship(back_populates="institution")
    import_batches: Mapped[list[DataImportBatch]] = relationship(back_populates="institution")
