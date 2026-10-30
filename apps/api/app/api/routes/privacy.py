from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.errors import request_id_for
from app.auth.dependencies import get_current_principal
from app.auth.policies import Principal
from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.enums import UserRole
from app.services.verification import (
    create_verifier_grant,
    grant_consent,
    issue_verification,
    revoke_consent,
    revoke_verifier_grant,
    verify_credential,
)

router = APIRouter(tags=["privacy and verification"])


class ConsentGrantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enrolment_id: uuid.UUID
    verifier_user_id: uuid.UUID
    purpose: str = Field(min_length=1, max_length=120)
    permitted_claims: set[str]


class VerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enrolment_id: uuid.UUID
    purpose: str = Field(min_length=1, max_length=120)
    claims: set[str]
    audience: str = Field(min_length=1, max_length=200)


class CredentialVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    credential: str = Field(min_length=1, max_length=10000)
    audience: str = Field(min_length=1, max_length=200)


class VerifierGrantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verifier_user_id: uuid.UUID
    purpose: str = Field(min_length=2, max_length=120)
    permitted_claims: set[str]
    expires_at: datetime


@router.post("/verification/grants", status_code=201, operation_id="createVerifierGrant")
def post_verifier_grant(
    payload: VerifierGrantRequest,
    request: Request,
    principal: Principal = Depends(get_current_principal),  # noqa: B008
    db: Session = Depends(get_db_session),  # noqa: B008
) -> dict:
    return create_verifier_grant(
        db,
        principal=principal,
        verifier_id=payload.verifier_user_id,
        purpose=payload.purpose,
        claims=payload.permitted_claims,
        expires_at=payload.expires_at,
        request_id=request_id_for(request),
    )


@router.post("/verification/grants/{grant_id}/revoke", operation_id="revokeVerifierGrant")
def post_revoke_verifier_grant(
    grant_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(get_current_principal),  # noqa: B008
    db: Session = Depends(get_db_session),  # noqa: B008
) -> dict:
    return revoke_verifier_grant(
        db, principal=principal, grant_id=grant_id, request_id=request_id_for(request)
    )


@router.post("/consents", status_code=201, operation_id="grantVerificationConsent")
def post_consent(
    payload: ConsentGrantRequest,
    request: Request,
    principal: Principal = Depends(get_current_principal),  # noqa: B008
    db: Session = Depends(get_db_session),  # noqa: B008
) -> dict:  # noqa: B008
    return grant_consent(
        db,
        principal=principal,
        enrolment_id=payload.enrolment_id,
        verifier_id=payload.verifier_user_id,
        purpose=payload.purpose,
        claims=payload.permitted_claims,
        request_id=request_id_for(request),
    )


@router.post("/consents/{consent_id}/revoke", operation_id="revokeVerificationConsent")
def post_revoke(
    consent_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(get_current_principal),  # noqa: B008
    db: Session = Depends(get_db_session),  # noqa: B008
) -> dict:  # noqa: B008
    return revoke_consent(
        db, principal=principal, consent_id=consent_id, request_id=request_id_for(request)
    )


@router.post("/verification/credentials", operation_id="createVerificationCredential")
def post_verification(
    payload: VerificationRequest,
    request: Request,
    principal: Principal = Depends(get_current_principal),  # noqa: B008
    db: Session = Depends(get_db_session),  # noqa: B008
) -> dict:  # noqa: B008
    if principal.role != UserRole.EXTERNAL_VERIFIER:
        raise HTTPException(403, "Only an authorized external verifier may request claims.")
    return issue_verification(
        db,
        principal=principal,
        enrolment_id=payload.enrolment_id,
        purpose=payload.purpose,
        claims=payload.claims,
        audience=payload.audience,
        request_id=request_id_for(request),
    )


@router.post("/verification/credentials/verify", operation_id="verifyCredential")
def post_verify_credential(
    payload: CredentialVerifyRequest,
    request: Request,
    principal: Principal = Depends(get_current_principal),  # noqa: B008
    db: Session = Depends(get_db_session),  # noqa: B008
) -> dict:  # noqa: B008
    secret = get_settings().verification_signing_private_key
    if secret is None:
        raise HTTPException(503, "Signed verification is not configured.")
    from app.services.verification import _private_key

    private = _private_key()
    return verify_credential(
        db,
        token=payload.credential,
        audience=payload.audience,
        public_key=private.public_key(),
        principal=principal,
        request_id=request_id_for(request),
    )
