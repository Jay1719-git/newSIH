from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from fastapi import HTTPException
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.models.verifier_grant import ExternalVerifierGrant


class Action(StrEnum):
    READ = "read"
    WRITE = "write"
    EXPORT = "export"
    INVESTIGATE = "investigate"
    VERIFY = "verify"


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    role: UserRole
    institution_id: uuid.UUID | None = None
    student_identity_reference_id: uuid.UUID | None = None
    auth_session_id: uuid.UUID | None = None


@dataclass(frozen=True)
class VerificationGrant:
    purpose: str
    permitted_claims: frozenset[str]
    expires_at: datetime


AICTE_ROLES = frozenset({UserRole.REGULATOR_ADMIN, UserRole.REGULATOR_OFFICER})
INSTITUTION_ROLES = frozenset({UserRole.INSTITUTION_ADMIN, UserRole.INSTITUTION_OPERATOR})
VERIFIER_CLAIMS = frozenset({"enrolment_status", "program_code", "academic_year", "consent_status"})


def authorize_record(
    principal: Principal,
    *,
    institution_id: uuid.UUID | None,
    action: Action,
    resource: str,
    student_identity_reference_id: uuid.UUID | None = None,
    purpose: str | None = None,
    claims: set[str] | frozenset[str] = frozenset(),
    grants: tuple[VerificationGrant, ...] = (),
    now: datetime | None = None,
) -> None:
    """Raise 403 unless a principal is permitted for this exact record and action."""
    role = principal.role
    if role in AICTE_ROLES:
        if action in {Action.READ, Action.EXPORT} and resource in {
            "institution_record",
            "audit",
            "compliance",
            "aggregate",
            "case",
        }:
            return
        if role == UserRole.REGULATOR_ADMIN and action == Action.INVESTIGATE and resource == "case":
            return
        raise HTTPException(status_code=403, detail="Operation is not permitted for this resource.")

    if role in INSTITUTION_ROLES:
        if not principal.institution_id or institution_id != principal.institution_id:
            raise HTTPException(status_code=404, detail="Resource not found.")
        if action == Action.READ and resource in {
            "audit",
            "compliance",
            "student_record",
            "aggregate",
            "case",
        }:
            return
        if (
            role == UserRole.INSTITUTION_ADMIN
            and action == Action.EXPORT
            and resource in {"audit", "compliance", "student_record"}
        ):
            return
        if action == Action.WRITE and resource in {"student_record", "batch", "consent"}:
            return
        raise HTTPException(status_code=403, detail="Operation is not permitted for this role.")

    if role == UserRole.AUDITOR:
        if action == Action.READ and resource in {"audit", "compliance"}:
            if principal.institution_id is not None and institution_id == principal.institution_id:
                return
        raise HTTPException(status_code=403, detail="Auditors have read-only audit access.")

    if role == UserRole.STUDENT:
        if (
            action == Action.READ
            and resource == "student_record"
            and principal.student_identity_reference_id is not None
            and student_identity_reference_id == principal.student_identity_reference_id
        ):
            return
        raise HTTPException(status_code=404, detail="Resource not found.")

    if role == UserRole.EXTERNAL_VERIFIER:
        moment = now or datetime.now(UTC)

        def grant_is_current(grant: VerificationGrant) -> bool:
            expires_at = grant.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            return expires_at > moment

        if (
            action == Action.VERIFY
            and resource == "verification"
            and purpose
            and set(claims) <= VERIFIER_CLAIMS
            and any(
                grant.purpose == purpose
                and grant_is_current(grant)
                and set(claims) <= grant.permitted_claims
                for grant in grants
            )
        ):
            return
        raise HTTPException(
            status_code=403, detail="Verification purpose or claims are not permitted."
        )

    raise HTTPException(status_code=403, detail="Operation is not permitted.")


def tenant_scope(statement: Select[Any], model: type[Any], principal: Principal) -> Select[Any]:
    """Add server-derived tenant filtering; callers cannot pass the tenant identity."""
    if principal.role in AICTE_ROLES:
        return statement
    if principal.role in INSTITUTION_ROLES or principal.role == UserRole.AUDITOR:
        if principal.institution_id is None:
            raise HTTPException(status_code=403, detail="Institution membership is required.")
        if (
            principal.role == UserRole.AUDITOR
            and getattr(model, "__tablename__", None) != "audit_events"
        ):
            raise HTTPException(status_code=403, detail="Auditors can query audit records only.")
        return statement.where(model.institution_id == principal.institution_id)
    raise HTTPException(
        status_code=403, detail="This role cannot query institution-scoped records."
    )


def authorize_external_verification(
    db: Session,
    principal: Principal,
    *,
    purpose: str,
    claims: set[str] | frozenset[str],
    now: datetime | None = None,
) -> None:
    """Load grants from PostgreSQL; never accept caller-supplied authorization grants."""
    moment = now or datetime.now(UTC)
    records = db.scalars(
        select(ExternalVerifierGrant).where(
            ExternalVerifierGrant.user_id == principal.user_id,
            ExternalVerifierGrant.purpose == purpose,
            ExternalVerifierGrant.expires_at > moment,
            ExternalVerifierGrant.revoked_at.is_(None),
        )
    )
    grants = tuple(
        VerificationGrant(
            purpose=record.purpose,
            permitted_claims=frozenset(record.permitted_claims),
            expires_at=record.expires_at,
        )
        for record in records
    )
    authorize_record(
        principal,
        institution_id=None,
        action=Action.VERIFY,
        resource="verification",
        purpose=purpose,
        claims=claims,
        grants=grants,
        now=moment,
    )
