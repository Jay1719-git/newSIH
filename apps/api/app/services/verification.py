from __future__ import annotations

import base64
import json
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.policies import Principal, authorize_external_verification
from app.core.config import get_settings
from app.models.academics import AcademicProgram, AcademicYear, ProgramAcademicYear
from app.models.consent import ConsentRecord
from app.models.enums import AuditEntityType, ConsentStatus, EnrolmentStatus, UserRole
from app.models.identity import Enrolment
from app.models.user import User
from app.models.verification_credential import VerificationCredential
from app.models.verifier_grant import ExternalVerifierGrant
from app.services.audit import append_audit

ALLOWED_CLAIMS = frozenset({"enrolment_status", "program_code", "academic_year", "award_status"})
_PURPOSE = re.compile(r"^[A-Z][A-Z0-9_]{1,119}$")


def consent_is_current(
    consent: ConsentRecord | None,
    *,
    verifier_id: uuid.UUID,
    purpose: str,
    claims: set[str],
    now: datetime | None = None,
) -> bool:
    moment = now or datetime.now(UTC)
    expiry = consent.expires_at if consent else None
    if expiry is not None and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    return bool(
        consent
        and consent.status == ConsentStatus.GRANTED
        and consent.verifier_user_id == verifier_id
        and consent.purpose == purpose
        and expiry is not None
        and expiry > moment
        and claims <= set(consent.permitted_claims or [])
    )


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _private_key() -> Ed25519PrivateKey:
    secret = get_settings().verification_signing_private_key
    if secret is None:
        raise HTTPException(503, "Signed verification is not configured.")
    try:
        key = serialization.load_der_private_key(_unb64(secret.get_secret_value()), password=None)
    except (ValueError, TypeError) as exc:
        raise HTTPException(503, "Verification signing key configuration is invalid.") from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise HTTPException(503, "Verification signing key must be Ed25519.")
    return key


def _issue_token(claims: dict, *, audience: str, jti: str, expires: datetime) -> str:
    header = {"alg": "EdDSA", "typ": "WEAVE-V1"}
    payload = {
        "iss": get_settings().verification_issuer,
        "aud": audience,
        "iat": int(datetime.now(UTC).timestamp()),
        "exp": int(expires.timestamp()),
        "jti": jti,
        "claims": claims,
    }
    encoded_header = _b64(json.dumps(header, sort_keys=True, separators=(",", ":")).encode())
    encoded_payload = _b64(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    signing_input = f"{encoded_header}.{encoded_payload}"
    return f"{signing_input}.{_b64(_private_key().sign(signing_input.encode()))}"


def verify_token(
    token: str, *, audience: str, public_key: Ed25519PublicKey, now: datetime | None = None
) -> dict:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        header = json.loads(_unb64(encoded_header))
        payload = json.loads(_unb64(encoded_payload))
        if header != {"alg": "EdDSA", "typ": "WEAVE-V1"}:
            raise ValueError
        public_key.verify(_unb64(encoded_signature), f"{encoded_header}.{encoded_payload}".encode())
    except Exception as exc:
        raise HTTPException(400, "Credential signature or encoding is invalid.") from exc
    current = int((now or datetime.now(UTC)).timestamp())
    if payload.get("iss") != get_settings().verification_issuer or payload.get("aud") != audience:
        raise HTTPException(403, "Credential issuer or audience does not match.")
    if not isinstance(payload.get("exp"), int) or payload["exp"] <= current:
        raise HTTPException(410, "Credential has expired.")
    if (
        not isinstance(payload.get("iat"), int)
        or payload["iat"] > current
        or not isinstance(payload.get("jti"), str)
        or not isinstance(payload.get("claims"), dict)
        or not set(payload["claims"]) <= ALLOWED_CLAIMS
    ):
        raise HTTPException(400, "Credential claims or timestamps are invalid.")
    return payload


def grant_consent(
    db: Session,
    *,
    principal: Principal,
    enrolment_id: uuid.UUID,
    verifier_id: uuid.UUID,
    purpose: str,
    claims: set[str],
    request_id: str,
) -> dict:
    if principal.role != UserRole.STUDENT or principal.student_identity_reference_id is None:
        raise HTTPException(403, "Only the authenticated student can grant this consent.")
    verifier = db.get(User, verifier_id)
    if verifier is None or verifier.role != UserRole.EXTERNAL_VERIFIER:
        raise HTTPException(422, "Consent must identify an external verifier account.")
    if not _PURPOSE.fullmatch(purpose) or not claims or not claims <= ALLOWED_CLAIMS:
        raise HTTPException(422, "Requested claims are not eligible for consent.")
    enrolment = db.get(Enrolment, enrolment_id)
    if (
        enrolment is None
        or enrolment.identity_reference_id != principal.student_identity_reference_id
    ):
        raise HTTPException(404, "Enrolment was not found.")
    grant = db.scalar(
        select(ConsentRecord)
        .where(
            ConsentRecord.enrolment_id == enrolment_id,
            ConsentRecord.verifier_user_id == verifier_id,
            ConsentRecord.purpose == purpose,
            ConsentRecord.status == ConsentStatus.GRANTED,
        )
        .with_for_update()
    )
    now = datetime.now(UTC)
    if grant is None:
        grant = ConsentRecord(
            enrolment_id=enrolment_id,
            verifier_user_id=verifier_id,
            status=ConsentStatus.GRANTED,
            purpose=purpose,
            permitted_claims=sorted(claims),
            recorded_at=now,
            expires_at=now + timedelta(days=30),
        )
        db.add(grant)
    else:
        grant.permitted_claims = sorted(claims)
        grant.recorded_at, grant.expires_at, grant.withdrawn_at = (
            now,
            now + timedelta(days=30),
            None,
        )
    append_audit(
        db,
        principal=principal,
        action="CONSENT_GRANTED",
        resource_type=AuditEntityType.CONSENT,
        resource_id=grant.id,
        institution_id=enrolment.institution_id,
        request_id=request_id,
        outcome="SUCCESS",
        metadata={"claim_names": ",".join(sorted(claims)), "purpose_code": purpose},
    )
    db.commit()
    return {
        "consent_id": str(grant.id),
        "status": grant.status.value,
        "permitted_claims": grant.permitted_claims,
        "expires_at": grant.expires_at.isoformat(),
    }


def revoke_consent(
    db: Session, *, principal: Principal, consent_id: uuid.UUID, request_id: str
) -> dict:
    consent = db.get(ConsentRecord, consent_id)
    if consent is None:
        raise HTTPException(404, "Consent record was not found.")
    enrolment = db.get(Enrolment, consent.enrolment_id)
    if (
        principal.role != UserRole.STUDENT
        or enrolment.identity_reference_id != principal.student_identity_reference_id
    ):
        raise HTTPException(404, "Consent record was not found.")
    now = datetime.now(UTC)
    consent.status, consent.withdrawn_at = ConsentStatus.WITHDRAWN, now
    credentials = db.scalars(
        select(VerificationCredential).where(
            VerificationCredential.enrolment_id == enrolment.id,
            VerificationCredential.verifier_user_id == consent.verifier_user_id,
            VerificationCredential.revoked_at.is_(None),
        )
    )
    for credential in credentials:
        credential.revoked_at = now
    append_audit(
        db,
        principal=principal,
        action="CONSENT_REVOKED",
        resource_type=AuditEntityType.CONSENT,
        resource_id=consent.id,
        institution_id=enrolment.institution_id,
        request_id=request_id,
        outcome="SUCCESS",
        metadata={"purpose_code": consent.purpose},
    )
    db.commit()
    return {
        "consent_id": str(consent.id),
        "status": consent.status.value,
        "revoked_at": now.isoformat(),
    }


def issue_verification(
    db: Session,
    *,
    principal: Principal,
    enrolment_id: uuid.UUID,
    purpose: str,
    claims: set[str],
    audience: str,
    request_id: str,
) -> dict:
    if (
        not _PURPOSE.fullmatch(purpose)
        or not audience
        or len(audience) > 200
        or not claims
        or not claims <= ALLOWED_CLAIMS
    ):
        raise HTTPException(422, "Audience and eligible claims are required.")
    authorize_external_verification(db, principal, purpose=purpose, claims=claims)
    now = datetime.now(UTC)
    consent = db.scalar(
        select(ConsentRecord).where(
            ConsentRecord.enrolment_id == enrolment_id,
            ConsentRecord.verifier_user_id == principal.user_id,
            ConsentRecord.purpose == purpose,
            ConsentRecord.status == ConsentStatus.GRANTED,
            ConsentRecord.expires_at > now,
        )
    )
    enrolment = db.get(Enrolment, enrolment_id)
    if (
        not consent_is_current(
            consent, verifier_id=principal.user_id, purpose=purpose, claims=claims, now=now
        )
        or enrolment is None
    ):
        append_audit(
            db,
            principal=principal,
            action="VERIFICATION_REQUESTED",
            resource_type=AuditEntityType.ENROLMENT,
            resource_id=enrolment_id,
            request_id=request_id,
            outcome="DENIED",
            metadata={"claim_names": ",".join(sorted(claims)), "purpose_code": purpose},
        )
        db.commit()
        raise HTTPException(
            403, "Active consent for this verifier, purpose and claims is required."
        )
    year = db.get(ProgramAcademicYear, enrolment.program_academic_year_id)
    program = db.get(AcademicProgram, year.program_id) if year else None
    academic_year = db.get(AcademicYear, year.academic_year_id) if year else None
    values = {
        "enrolment_status": enrolment.status.value,
        "program_code": program.code if program else None,
        "academic_year": academic_year.label if academic_year else None,
        "award_status": "AWARDED"
        if enrolment.status == EnrolmentStatus.ACCEPTED
        else "NOT_RECORDED",
    }
    presented = {claim: values[claim] for claim in sorted(claims) if values.get(claim) is not None}
    jti, expires = secrets.token_urlsafe(24), now + timedelta(minutes=5)
    db.add(
        VerificationCredential(
            jti=jti,
            verifier_user_id=principal.user_id,
            enrolment_id=enrolment.id,
            expires_at=expires,
        )
    )
    token = _issue_token(presented, audience=audience, jti=jti, expires=expires)
    append_audit(
        db,
        principal=principal,
        action="VERIFICATION_REQUESTED",
        resource_type=AuditEntityType.ENROLMENT,
        resource_id=enrolment.id,
        institution_id=enrolment.institution_id,
        request_id=request_id,
        outcome="SUCCESS",
        metadata={"claim_names": ",".join(presented), "purpose_code": purpose},
    )
    db.commit()
    return {
        "credential": token,
        "issuer": get_settings().verification_issuer,
        "audience": audience,
        "claims": presented,
        "expires_at": expires.isoformat(),
        "source": "WEAVE_RECORD_CHECK",
        "external_verification": "NOT_PERFORMED",
    }


def verify_credential(
    db: Session,
    *,
    token: str,
    audience: str,
    public_key: Ed25519PublicKey,
    principal: Principal,
    request_id: str,
) -> dict:
    payload = verify_token(token, audience=audience, public_key=public_key)
    row = db.scalar(
        select(VerificationCredential).where(VerificationCredential.jti == payload["jti"])
    )
    if row is None or row.revoked_at is not None or row.expires_at <= datetime.now(UTC):
        raise HTTPException(410, "Credential is revoked or unavailable.")
    if principal.role != UserRole.EXTERNAL_VERIFIER or principal.user_id != row.verifier_user_id:
        raise HTTPException(403, "This credential is not available to this verifier.")
    enrolment = db.get(Enrolment, row.enrolment_id)
    append_audit(
        db,
        principal=principal,
        action="VERIFICATION_CREDENTIAL_CHECKED",
        resource_type=AuditEntityType.ENROLMENT,
        resource_id=row.enrolment_id,
        institution_id=enrolment.institution_id if enrolment else None,
        request_id=request_id,
        outcome="SUCCESS",
        metadata={"claim_names": ",".join(sorted(payload["claims"]))},
    )
    db.commit()
    return {
        "valid": True,
        "issuer": payload["iss"],
        "audience": payload["aud"],
        "claims": payload["claims"],
        "expires_at": datetime.fromtimestamp(payload["exp"], UTC).isoformat(),
    }


def create_verifier_grant(
    db: Session,
    *,
    principal: Principal,
    verifier_id: uuid.UUID,
    purpose: str,
    claims: set[str],
    expires_at: datetime,
    request_id: str,
) -> dict:
    if principal.role != UserRole.REGULATOR_ADMIN:
        raise HTTPException(403, "Only a regulator administrator may change verifier permissions.")
    verifier = db.get(User, verifier_id)
    now = datetime.now(UTC)
    expiry = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=UTC)
    if verifier is None or verifier.role != UserRole.EXTERNAL_VERIFIER:
        raise HTTPException(422, "Grant must target an external verifier account.")
    if (
        not _PURPOSE.fullmatch(purpose)
        or not claims
        or not claims <= ALLOWED_CLAIMS
        or expiry <= now
    ):
        raise HTTPException(422, "Grant purpose, claims or expiry are invalid.")
    grant = ExternalVerifierGrant(
        user_id=verifier_id,
        purpose=purpose,
        permitted_claims=sorted(claims),
        expires_at=expiry,
        approved_by_user_id=principal.user_id,
    )
    db.add(grant)
    db.flush()
    append_audit(
        db,
        principal=principal,
        action="VERIFIER_PERMISSION_GRANTED",
        resource_type=AuditEntityType.USER,
        resource_id=verifier_id,
        request_id=request_id,
        outcome="SUCCESS",
        metadata={"claim_names": ",".join(sorted(claims)), "purpose_code": purpose},
    )
    db.commit()
    return {
        "grant_id": str(grant.id),
        "verifier_user_id": str(verifier_id),
        "purpose": purpose,
        "permitted_claims": grant.permitted_claims,
        "expires_at": expiry.isoformat(),
    }


def revoke_verifier_grant(
    db: Session, *, principal: Principal, grant_id: uuid.UUID, request_id: str
) -> dict:
    if principal.role != UserRole.REGULATOR_ADMIN:
        raise HTTPException(403, "Only a regulator administrator may change verifier permissions.")
    grant = db.get(ExternalVerifierGrant, grant_id)
    if grant is None:
        raise HTTPException(404, "Verifier grant was not found.")
    grant.revoked_at = datetime.now(UTC)
    append_audit(
        db,
        principal=principal,
        action="VERIFIER_PERMISSION_REVOKED",
        resource_type=AuditEntityType.USER,
        resource_id=grant.user_id,
        request_id=request_id,
        outcome="SUCCESS",
        metadata={"purpose_code": grant.purpose},
    )
    db.commit()
    return {"grant_id": str(grant.id), "revoked": True, "revoked_at": grant.revoked_at.isoformat()}
