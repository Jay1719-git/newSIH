from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.auth.passwords import hash_password, verify_password
from app.auth.policies import (
    Action,
    Principal,
    VerificationGrant,
    authorize_record,
    tenant_scope,
)
from app.auth.throttle import LoginThrottle
from app.models.audit import AuditEvent
from app.models.enums import UserRole
from app.models.identity import Enrolment


def test_institution_membership_scopes_records_and_denies_idor_actions() -> None:
    own, other = uuid4(), uuid4()
    principal = Principal(uuid4(), UserRole.INSTITUTION_OPERATOR, institution_id=own)
    authorize_record(
        principal,
        institution_id=own,
        action=Action.READ,
        resource="student_record",
    )
    for action in (Action.READ, Action.WRITE, Action.EXPORT):
        with pytest.raises(HTTPException) as error:
            authorize_record(
                principal,
                institution_id=other,
                action=action,
                resource="student_record",
            )
        assert error.value.status_code == 404

    sql = tenant_scope(select(Enrolment), Enrolment, principal).compile(
        compile_kwargs={"literal_binds": True}
    )
    assert own.hex in str(sql)
    assert other.hex not in str(sql)


def test_student_can_only_read_own_identity_record() -> None:
    own, other = uuid4(), uuid4()
    principal = Principal(uuid4(), UserRole.STUDENT, student_identity_reference_id=own)
    authorize_record(
        principal,
        institution_id=None,
        student_identity_reference_id=own,
        action=Action.READ,
        resource="student_record",
    )
    with pytest.raises(HTTPException) as error:
        authorize_record(
            principal,
            institution_id=None,
            student_identity_reference_id=other,
            action=Action.READ,
            resource="student_record",
        )
    assert error.value.status_code == 404
    with pytest.raises(HTTPException) as enumeration:
        tenant_scope(select(Enrolment), Enrolment, principal)
    assert enumeration.value.status_code == 403


def test_auditor_is_read_only_and_institution_scoped() -> None:
    institution = uuid4()
    auditor = Principal(uuid4(), UserRole.AUDITOR, institution_id=institution)
    authorize_record(auditor, institution_id=institution, action=Action.READ, resource="audit")
    with pytest.raises(HTTPException) as denied_mutation:
        authorize_record(auditor, institution_id=institution, action=Action.WRITE, resource="audit")
    assert denied_mutation.value.status_code == 403
    with pytest.raises(HTTPException) as denied_other_tenant:
        authorize_record(auditor, institution_id=uuid4(), action=Action.READ, resource="audit")
    assert denied_other_tenant.value.status_code == 403
    scoped_audits = tenant_scope(select(AuditEvent), AuditEvent, auditor).compile(
        compile_kwargs={"literal_binds": True}
    )
    assert institution.hex in str(scoped_audits)
    with pytest.raises(HTTPException):
        tenant_scope(select(Enrolment), Enrolment, auditor)


def test_external_verifier_is_limited_to_granted_purpose_and_claims() -> None:
    principal = Principal(uuid4(), UserRole.EXTERNAL_VERIFIER)
    now = datetime.now(UTC)
    grant = VerificationGrant(
        "admissions", frozenset({"enrolment_status"}), now + timedelta(minutes=5)
    )
    authorize_record(
        principal,
        institution_id=None,
        action=Action.VERIFY,
        resource="verification",
        purpose="admissions",
        claims={"enrolment_status"},
        grants=(grant,),
        now=now,
    )
    with pytest.raises(HTTPException):
        authorize_record(
            principal,
            institution_id=None,
            action=Action.VERIFY,
            resource="verification",
            purpose="admissions",
            claims={"full_name"},
            grants=(grant,),
            now=now,
        )


def test_aicte_roles_and_institution_admin_have_distinct_write_authority() -> None:
    institution = uuid4()
    officer = Principal(uuid4(), UserRole.REGULATOR_OFFICER)
    authorize_record(officer, institution_id=None, action=Action.READ, resource="aggregate")
    with pytest.raises(HTTPException):
        authorize_record(officer, institution_id=None, action=Action.INVESTIGATE, resource="case")

    admin = Principal(uuid4(), UserRole.REGULATOR_ADMIN)
    authorize_record(admin, institution_id=None, action=Action.INVESTIGATE, resource="case")
    with pytest.raises(HTTPException):
        authorize_record(
            admin, institution_id=institution, action=Action.READ, resource="student_record"
        )
    with pytest.raises(HTTPException):
        authorize_record(
            admin, institution_id=institution, action=Action.WRITE, resource="student_record"
        )

    institution_admin = Principal(uuid4(), UserRole.INSTITUTION_ADMIN, institution_id=institution)
    authorize_record(
        institution_admin,
        institution_id=institution,
        action=Action.WRITE,
        resource="student_record",
    )


def test_password_hash_is_salted_and_verified() -> None:
    first = hash_password("synthetic-safe-password")
    second = hash_password("synthetic-safe-password")
    assert first != second
    assert verify_password("synthetic-safe-password", first)
    assert not verify_password("different-password", first)
    assert not verify_password("synthetic-safe-password", None)


def test_login_throttle_blocks_repeated_failures_without_retaining_email() -> None:
    throttle = LoginThrottle(attempts=2, window_seconds=60, block_seconds=30)
    throttle.record_failure("127.0.0.1", "synthetic@example.test", now=10)
    throttle.record_failure("127.0.0.1", "synthetic@example.test", now=11)
    assert throttle.is_blocked("127.0.0.1", "synthetic@example.test", now=12)
    assert "synthetic@example.test" not in repr(throttle._failures)
