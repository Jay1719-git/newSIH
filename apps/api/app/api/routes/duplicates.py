from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.errors import request_id_for
from app.auth.dependencies import get_current_principal
from app.auth.policies import Principal
from app.db.session import get_db_session
from app.models.duplicate import DuplicateCase
from app.models.enums import AuditEntityType
from app.schemas.duplicates import DuplicateDecisionRequest
from app.services.audit import append_audit
from app.services.duplicate_detection import (
    decide_duplicate_case,
    list_duplicate_cases,
    scan_duplicates,
)

router = APIRouter(prefix="/students/duplicates", tags=["duplicate detection"])


@router.post("/scan", operation_id="scanStudentDuplicates")
def scan_student_duplicates(
    principal: Principal = Depends(get_current_principal),  # noqa: B008
    db: Session = Depends(get_db_session),  # noqa: B008
) -> dict:
    return scan_duplicates(db, principal=principal)


@router.get("", operation_id="listDuplicateCases")
def get_duplicate_cases(
    principal: Principal = Depends(get_current_principal),  # noqa: B008
    db: Session = Depends(get_db_session),  # noqa: B008
) -> dict:
    return list_duplicate_cases(db, principal=principal)


@router.post("/{case_id}/decisions", operation_id="decideDuplicateCase")
def post_duplicate_decision(
    case_id: uuid.UUID,
    payload: DuplicateDecisionRequest,
    request: Request,
    principal: Principal = Depends(get_current_principal),  # noqa: B008
    db: Session = Depends(get_db_session),  # noqa: B008
) -> dict:
    result = decide_duplicate_case(
        db,
        principal=principal,
        case_id=case_id,
        outcome=payload.outcome,
    )
    case = db.get(DuplicateCase, case_id)
    append_audit(
        db,
        principal=principal,
        action="REVIEW_CASE_DECISION",
        resource_type=AuditEntityType.REVIEW_CASE,
        resource_id=case_id,
        institution_id=case.institution_a_id if case else principal.institution_id,
        request_id=request_id_for(request),
        outcome="SUCCESS",
        metadata={"reason_code": payload.outcome},
    )
    db.commit()
    return result
