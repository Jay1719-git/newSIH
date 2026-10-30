from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_principal
from app.auth.policies import Action, Principal, authorize_record
from app.db.session import get_db_session
from app.models.academics import AcademicProgram, AcademicYear, ApprovedIntake, ProgramAcademicYear
from app.models.enums import EnrolmentStatus, UserRole
from app.models.identity import Enrolment
from app.models.institution import Institution

router = APIRouter(prefix="/institutions", tags=["institutions"])


@router.get("/me", operation_id="getInstitutionsOverview")
def get_institutions_overview(
    principal: Principal = Depends(get_current_principal),  # noqa: B008
    db: Session = Depends(get_db_session),  # noqa: B008
) -> dict:
    authorize_record(
        principal,
        institution_id=principal.institution_id,
        action=Action.READ,
        resource="aggregate",
    )
    if principal.role in {UserRole.INSTITUTION_ADMIN, UserRole.INSTITUTION_OPERATOR}:
        institutions = list(
            db.scalars(select(Institution).where(Institution.id == principal.institution_id))
        )
    else:
        institutions = list(db.scalars(select(Institution).order_by(Institution.name)))

    summaries = []
    for institution in institutions:
        programs = list(
            db.execute(
                select(AcademicProgram, ProgramAcademicYear, AcademicYear)
                .join(ProgramAcademicYear, ProgramAcademicYear.program_id == AcademicProgram.id)
                .join(AcademicYear, ProgramAcademicYear.academic_year_id == AcademicYear.id)
                .where(ProgramAcademicYear.institution_id == institution.id)
                .order_by(AcademicProgram.code, AcademicYear.starts_on.desc())
            )
        )
        program_slices = []
        for program, program_year, academic_year in programs:
            intake_rows = list(
                db.scalars(
                    select(ApprovedIntake).where(
                        ApprovedIntake.program_academic_year_id == program_year.id
                    )
                )
            )
            total_pool = next(
                (row.approved_seats for row in intake_rows if row.seat_category_id is None), None
            )
            approved = (
                total_pool
                if total_pool is not None
                else sum(row.approved_seats for row in intake_rows)
            )
            enrolment_statuses = Counter(
                db.scalars(
                    select(Enrolment.status).where(
                        Enrolment.program_academic_year_id == program_year.id,
                        Enrolment.institution_id == institution.id,
                    )
                )
            )
            verified = (
                enrolment_statuses[EnrolmentStatus.ACCEPTED]
                + enrolment_statuses[EnrolmentStatus.VERIFIED]
            )
            pending = (
                enrolment_statuses[EnrolmentStatus.PENDING_REVIEW]
                + enrolment_statuses[EnrolmentStatus.FLAGGED_CONFLICT]
            )
            program_slices.append(
                {
                    "program_code": program.code,
                    "program_title": program.title,
                    "approved_intake": approved,
                    "enrolled_verified": verified,
                    "flagged_or_pending": pending,
                    "academic_year": academic_year.code,
                }
            )
        summaries.append(
            {
                "id": str(institution.id),
                "aicte_code": institution.aicte_code,
                "name": institution.name,
                "state": institution.state,
                "tier": institution.tier,
                "status": institution.status.value,
                "programs": program_slices,
            }
        )
    return {
        "environment": "SYNTHETIC",
        "active_institution_id": str(principal.institution_id) if principal.institution_id else "",
        "role": principal.role.value,
        "institutions": summaries,
        "all_institutions": summaries,
    }
