from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import HTTPException

from app.auth.policies import Principal
from app.models.audit import AuditEvent
from app.models.consent import ConsentRecord
from app.models.enums import AuditEntityType, ConsentStatus, UserRole
from app.services.audit import safe_metadata, verify_audit_chain
from app.services.verification import (
    _b64,
    consent_is_current,
    create_verifier_grant,
    verify_token,
)


def _credential(
    private: Ed25519PrivateKey, *, audience: str = "test-verifier", exp: int | None = None
) -> str:
    header = _b64(b'{"alg":"EdDSA","typ":"WEAVE-V1"}')
    payload = _b64(
        json.dumps(
            {
                "iss": "weave.local",
                "aud": audience,
                "iat": int(datetime.now(UTC).timestamp()),
                "exp": exp or int((datetime.now(UTC) + timedelta(minutes=1)).timestamp()),
                "jti": "opaque",
                "claims": {"enrolment_status": "ACCEPTED"},
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    )
    signed = f"{header}.{payload}"
    return f"{signed}.{_b64(private.sign(signed.encode()))}"


def test_audit_metadata_allowlist_redacts_personal_values() -> None:
    assert safe_metadata(
        {
            "claim_names": "program_code",
            "email": "student@example.test",
            "apaar_id": "123456789012",
            "summary": "student name",
        }
    ) == {"claim_names": "program_code"}


def test_audit_hash_chain_detects_tampering() -> None:
    event_id, actor, institution, resource, created = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        datetime.now(UTC),
    )
    payload = {"outcome": "SUCCESS", "_serialization_version": 2, "claim_names": "program_code"}
    material = {
        "id": str(event_id),
        "institution_id": str(institution),
        "actor_user_id": str(actor),
        "action": "DATA_EXPORT",
        "resource_type": "IMPORT_BATCH",
        "resource_id": str(resource),
        "timestamp": created.isoformat(),
        "request_id": "req-test",
        "payload": payload,
        "previous_hash": None,
    }
    digest = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    event = AuditEvent(
        id=event_id,
        institution_id=institution,
        actor_user_id=actor,
        action="DATA_EXPORT",
        entity_type=AuditEntityType.IMPORT_BATCH,
        entity_id=resource,
        request_id="req-test",
        summary="export",
        payload=payload,
        previous_hash=None,
        event_hash=digest,
        created_at=created,
    )
    assert verify_audit_chain([event])
    event.payload = {**payload, "claim_names": "altered"}
    assert not verify_audit_chain([event])


def test_consent_revocation_and_expiry_prevent_claim_release() -> None:
    verifier_id = uuid4()
    consent = ConsentRecord(
        verifier_user_id=verifier_id,
        status=ConsentStatus.GRANTED,
        purpose="ENROLMENT_CHECK",
        permitted_claims=["enrolment_status"],
        expires_at=datetime.now(UTC) + timedelta(minutes=1),
    )
    args = {
        "verifier_id": verifier_id,
        "purpose": "ENROLMENT_CHECK",
        "claims": {"enrolment_status"},
    }
    assert consent_is_current(consent, **args)
    consent.status = ConsentStatus.WITHDRAWN
    assert not consent_is_current(consent, **args)
    consent.status = ConsentStatus.GRANTED
    consent.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert not consent_is_current(consent, **args)


def test_non_admin_cannot_change_verifier_permissions() -> None:
    principal = Principal(user_id=uuid4(), role=UserRole.EXTERNAL_VERIFIER)
    with pytest.raises(HTTPException) as denied:
        create_verifier_grant(
            object(),
            principal=principal,
            verifier_id=uuid4(),
            purpose="ENROLMENT_CHECK",
            claims={"enrolment_status"},
            expires_at=datetime.now(UTC) + timedelta(days=1),
            request_id="req-test",
        )
    assert denied.value.status_code == 403


def test_signed_credential_validates_signature_audience_expiry_and_tampering() -> None:
    private = Ed25519PrivateKey.generate()
    token = _credential(private)
    assert verify_token(token, audience="test-verifier", public_key=private.public_key())[
        "claims"
    ] == {"enrolment_status": "ACCEPTED"}
    with pytest.raises(HTTPException) as wrong_audience:
        verify_token(token, audience="other", public_key=private.public_key())
    assert wrong_audience.value.status_code == 403
    with pytest.raises(HTTPException) as expired:
        verify_token(
            _credential(private, exp=1), audience="test-verifier", public_key=private.public_key()
        )
    assert expired.value.status_code == 410
    pieces = token.split(".")
    signature = pieces[2]
    pieces[2] = ("A" if signature[0] != "A" else "B") + signature[1:]
    altered = ".".join(pieces)
    with pytest.raises(HTTPException) as signature:
        verify_token(altered, audience="test-verifier", public_key=private.public_key())
    assert signature.value.status_code == 400
