from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime
from getpass import getpass
from pathlib import Path
from uuid import UUID, uuid5

from sqlalchemy import select, text, update
from sqlalchemy.engine import make_url

from app import models as _models  # noqa: F401
from app.auth.passwords import hash_password
from app.auth.policies import VERIFIER_CLAIMS
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_engine, get_session_factory
from app.demo_data import generate_demo_datasets
from app.models.academics import (
    AcademicProgram,
    AcademicYear,
    ApprovedIntake,
    ProgramAcademicYear,
    SeatCategory,
)
from app.models.auth_session import AuthSession
from app.models.enums import (
    AcademicYearStatus,
    InstitutionStatus,
    ProgramStatus,
    UserRole,
    UserStatus,
)
from app.models.institution import Institution
from app.models.user import User
from app.models.verifier_grant import ExternalVerifierGrant

SYNTHETIC_EMAIL_SUFFIXES = (".synth.edu", ".synth.gov.in", ".synth.org", ".example.test")
DEMO_NAMESPACE = UUID("c191c81e-f73b-4cf4-a91b-7a4c1dc2a238")
DEMO_RESET_CONFIRMATION = "RESET-WEAVE-DEMO"


def require_local_demo_database() -> None:
    settings = get_settings()
    if settings.database_url is None:
        raise SystemExit("DATABASE_URL must point to the local synthetic demo database.")
    url = make_url(settings.database_url.get_secret_value())
    if (
        settings.app_env != "synthetic"
        or url.host not in {"localhost", "127.0.0.1", "::1"}
        or url.database != "weave_demo"
    ):
        raise SystemExit(
            "Demo seed/reset commands require APP_ENV=synthetic and local database weave_demo."
        )


def _demo_id(label: str) -> UUID:
    return uuid5(DEMO_NAMESPACE, label)


def seed_demo() -> None:
    require_local_demo_database()
    kkr_id, delhi_id = _demo_id("institution-kkr"), _demo_id("institution-delhi")
    year_id, open_seat_id = _demo_id("academic-year-2026"), _demo_id("seat-open")
    institutions = [
        Institution(
            id=kkr_id,
            aicte_code="SYNTH-KKR-001",
            name="Synthetic Institute Kurukshetra",
            state="Synthetic Haryana",
            tier="Synthetic",
            status=InstitutionStatus.ACTIVE,
        ),
        Institution(
            id=delhi_id,
            aicte_code="SYNTH-DEL-002",
            name="Synthetic Institute Delhi",
            state="Synthetic Delhi",
            tier="Synthetic",
            status=InstitutionStatus.ACTIVE,
        ),
    ]
    with get_session_factory()() as db, db.begin():
        for institution in institutions:
            existing = db.get(Institution, institution.id)
            if existing is None:
                db.add(institution)
        year = db.get(AcademicYear, year_id)
        if year is None:
            db.add(
                AcademicYear(
                    id=year_id,
                    code="SYNTH-AY-2026",
                    starts_on=datetime(2026, 1, 1).date(),
                    ends_on=datetime(2026, 12, 31).date(),
                    status=AcademicYearStatus.ACTIVE,
                )
            )
        seat = db.get(SeatCategory, open_seat_id)
        if seat is None:
            db.add(
                SeatCategory(
                    id=open_seat_id, code="OPEN", label="Synthetic Open Category", is_active=True
                )
            )
        db.flush()
        for institution_id, prefix in ((kkr_id, "KKR"), (delhi_id, "DEL")):
            program_id, program_year_id = (
                _demo_id(f"program-{prefix}"),
                _demo_id(f"program-year-{prefix}-2026"),
            )
            if db.get(AcademicProgram, program_id) is None:
                db.add(
                    AcademicProgram(
                        id=program_id,
                        institution_id=institution_id,
                        code="BTECH-CSE",
                        title="Synthetic Bachelor of Technology in Computer Science",
                        status=ProgramStatus.ACTIVE,
                    )
                )
            if db.get(ProgramAcademicYear, program_year_id) is None:
                db.add(
                    ProgramAcademicYear(
                        id=program_year_id,
                        institution_id=institution_id,
                        program_id=program_id,
                        academic_year_id=year_id,
                    )
                )
            db.flush()
            total_id, category_id = (
                _demo_id(f"intake-total-{prefix}"),
                _demo_id(f"intake-open-{prefix}"),
            )
            if db.get(ApprovedIntake, total_id) is None:
                db.add(
                    ApprovedIntake(
                        id=total_id,
                        program_academic_year_id=program_year_id,
                        seat_category_id=None,
                        approved_seats=2,
                    )
                )
            if db.get(ApprovedIntake, category_id) is None:
                db.add(
                    ApprovedIntake(
                        id=category_id,
                        program_academic_year_id=program_year_id,
                        seat_category_id=open_seat_id,
                        approved_seats=2,
                    )
                )
        db.flush()
    output_dir = Path(__file__).resolve().parents[3] / "synthetic" / "generated"
    generate_demo_datasets(output_dir)
    print("Seeded two synthetic institutions, one programme/year each, and approved capacity.")
    print(f"SYNTH-KKR-001 institution UUID: {kkr_id}")
    print(f"SYNTH-DEL-002 institution UUID: {delhi_id}")
    print(f"Generated deterministic CSV scenarios at {output_dir}.")


def reset_demo(confirmation: str | None) -> None:
    require_local_demo_database()
    if (
        confirmation != DEMO_RESET_CONFIRMATION
        or os.environ.get("WEAVE_ALLOW_DEMO_RESET") != "I_UNDERSTAND"
    ):
        raise SystemExit(
            "Reset refused. Pass --confirm-demo-reset RESET-WEAVE-DEMO and set "
            "WEAVE_ALLOW_DEMO_RESET=I_UNDERSTAND."
        )
    engine = get_engine()
    tables = sorted(Base.metadata.tables)
    quoted_tables = ", ".join(engine.dialect.identifier_preparer.quote(name) for name in tables)
    with engine.begin() as connection:
        if quoted_tables:
            connection.execute(text(f"TRUNCATE TABLE {quoted_tables} RESTART IDENTITY CASCADE"))
    print(
        "Cleared synthetic application records from local database weave_demo. "
        "Alembic history was preserved."
    )


def _validate_synthetic_email(email: str) -> None:
    if not any(email.endswith(suffix) for suffix in SYNTHETIC_EMAIL_SUFFIXES):
        raise SystemExit("Use a synthetic email domain (.synth.* or .example.test).")


def create_user() -> None:
    email = input("Account email: ").strip().casefold()
    _validate_synthetic_email(email)
    display_name = input("Display name: ").strip()
    role = UserRole(input(f"Role ({', '.join(item.value for item in UserRole)}): ").strip())
    institution_id = None
    student_identity_reference_id = None
    if role in {UserRole.INSTITUTION_ADMIN, UserRole.INSTITUTION_OPERATOR, UserRole.AUDITOR}:
        institution_id = UUID(input("Institution UUID: ").strip())
    if role == UserRole.STUDENT:
        student_identity_reference_id = UUID(input("Student identity reference UUID: ").strip())
    password = getpass("Initial password (12+ characters): ")
    confirmation = getpass("Confirm initial password: ")
    if password != confirmation:
        raise SystemExit("Passwords did not match.")
    encoded_password = hash_password(password)

    with get_session_factory()() as db:
        if db.scalar(select(User.id).where(User.email == email)):
            raise SystemExit("An account with that email already exists.")
        user = User(
            email=email,
            display_name=display_name,
            role=role,
            institution_id=institution_id,
            student_identity_reference_id=student_identity_reference_id,
            password_hash=encoded_password,
        )
        db.add(user)
        db.commit()
        print(f"Created account {user.id} with role {user.role.value}.")


def set_password() -> None:
    email = input("Account email: ").strip().casefold()
    _validate_synthetic_email(email)
    password = getpass("New password (12+ characters): ")
    confirmation = getpass("Confirm new password: ")
    if password != confirmation:
        raise SystemExit("Passwords did not match.")
    encoded_password = hash_password(password)
    with get_session_factory()() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            raise SystemExit("Account not found.")
        user.password_hash = encoded_password
        db.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        db.commit()
        print(f"Updated password for account {user.id}.")


def grant_verifier() -> None:
    verifier_id = UUID(input("External verifier user UUID: ").strip())
    approver_id = UUID(input("AICTE administrator user UUID: ").strip())
    purpose = input("Approved verification purpose: ").strip()
    claims = frozenset(
        claim.strip()
        for claim in input("Permitted claims (comma-separated): ").split(",")
        if claim.strip()
    )
    hours = int(input("Grant lifetime in hours (1-720): ").strip())
    if not purpose or len(purpose) > 120:
        raise SystemExit("Purpose must be between 1 and 120 characters.")
    if not claims or not claims <= VERIFIER_CLAIMS:
        raise SystemExit(f"Claims must be selected from: {', '.join(sorted(VERIFIER_CLAIMS))}.")
    if not 1 <= hours <= 720:
        raise SystemExit("Grant lifetime must be between 1 and 720 hours.")

    from datetime import timedelta

    with get_session_factory()() as db:
        verifier, approver = db.get(User, verifier_id), db.get(User, approver_id)
        if (
            verifier is None
            or verifier.role != UserRole.EXTERNAL_VERIFIER
            or verifier.status != UserStatus.ACTIVE
        ):
            raise SystemExit("The target account is not an external verifier.")
        if (
            approver is None
            or approver.role != UserRole.REGULATOR_ADMIN
            or approver.status != UserStatus.ACTIVE
        ):
            raise SystemExit("Grant approval requires an AICTE administrator account.")
        db.add(
            ExternalVerifierGrant(
                user_id=verifier.id,
                approved_by_user_id=approver.id,
                purpose=purpose,
                permitted_claims=sorted(claims),
                expires_at=datetime.now(UTC) + timedelta(hours=hours),
            )
        )
        db.commit()
        print("Created a time-limited, claim-scoped verification grant.")


def main() -> None:
    parser = argparse.ArgumentParser(description="WEAVE local account administration")
    parser.add_argument(
        "command",
        choices=["create-user", "set-password", "grant-verifier", "seed-demo", "reset-demo"],
    )
    parser.add_argument("--confirm-demo-reset")
    args = parser.parse_args()
    if args.command == "create-user":
        create_user()
    elif args.command == "set-password":
        set_password()
    elif args.command == "grant-verifier":
        grant_verifier()
    elif args.command == "seed-demo":
        seed_demo()
    elif args.command == "reset-demo":
        reset_demo(args.confirm_demo_reset)


if __name__ == "__main__":
    main()
