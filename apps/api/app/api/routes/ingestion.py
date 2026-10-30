from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import Response as RawResponse
from sqlalchemy.orm import Session

from app.api.errors import error_response, request_id_for
from app.auth.dependencies import get_current_principal
from app.auth.policies import Action, Principal, authorize_record
from app.db.session import get_db_session
from app.models.enums import AuditEntityType, UserRole
from app.models.ingestion import DataImportBatch
from app.schemas.ingestion import UploadBatchRequest
from app.services.audit import append_audit
from app.services.csv_ingestion import CsvStructureError
from app.services.ingestion import (
    commit_batch,
    error_report,
    get_batch,
    list_validation_results,
    upload_batch,
)

router = APIRouter(prefix="/students", tags=["student ingestion"])
INSTITUTION_ROLES = (UserRole.INSTITUTION_ADMIN, UserRole.INSTITUTION_OPERATOR)


def _authorize_read(principal: Principal, resource: str = "student_record") -> None:
    authorize_record(
        principal,
        institution_id=principal.institution_id,
        action=Action.READ,
        resource=resource,
    )


@router.post("/batches/upload", status_code=201, operation_id="uploadStudentBatch")
def upload_student_batch(
    payload: UploadBatchRequest,
    request: Request,
    response: Response,
    principal: Principal = Depends(get_current_principal),  # noqa: B008
    db: Session = Depends(get_db_session),  # noqa: B008
) -> dict:
    try:
        result = upload_batch(
            db,
            principal=principal,
            filename=payload.filename,
            csv_content=payload.csv_content,
            request_id=request_id_for(request),
        )
        if result.get("idempotent_replay"):
            response.status_code = 200
        return result
    except CsvStructureError as exc:
        return error_response(request, 400, "MALFORMED_CSV", str(exc))


@router.get("/batches/{batch_id}", operation_id="getStudentBatch")
def get_student_batch(
    batch_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),  # noqa: B008
    db: Session = Depends(get_db_session),  # noqa: B008
) -> dict:
    _authorize_read(principal)
    return get_batch(db, principal=principal, batch_id=batch_id)


@router.get("/validation-results", operation_id="getValidationResults")
def get_student_validation_results(
    principal: Principal = Depends(get_current_principal),  # noqa: B008
    db: Session = Depends(get_db_session),  # noqa: B008
) -> dict:
    _authorize_read(principal)
    return list_validation_results(db, principal=principal)


@router.get("/batches/{batch_id}/error-report", operation_id="downloadStudentBatchErrorReport")
def download_student_batch_error_report(
    batch_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(get_current_principal),  # noqa: B008
    db: Session = Depends(get_db_session),  # noqa: B008
) -> Response:
    authorize_record(
        principal,
        institution_id=principal.institution_id,
        action=Action.EXPORT,
        resource="student_record",
    )
    content = error_report(db, principal=principal, batch_id=batch_id)
    batch = db.get(DataImportBatch, batch_id)
    append_audit(
        db,
        principal=principal,
        action="DATA_EXPORT",
        resource_type=AuditEntityType.IMPORT_BATCH,
        resource_id=batch_id,
        institution_id=batch.institution_id if batch else principal.institution_id,
        request_id=request_id_for(request),
        outcome="SUCCESS",
        metadata={"format": "validation_csv"},
    )
    db.commit()
    return RawResponse(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="weave-batch-{batch_id}-errors.csv"'
        },
    )


@router.post("/batches/{batch_id}/commit", operation_id="commitStudentBatch")
def commit_student_batch(
    batch_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(get_current_principal),  # noqa: B008
    db: Session = Depends(get_db_session),  # noqa: B008
) -> dict:
    return commit_batch(
        db,
        principal=principal,
        batch_id=batch_id,
        request_id=request_id_for(request),
    )
