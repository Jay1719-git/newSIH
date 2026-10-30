from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.auth.dependencies import get_current_principal
from app.auth.policies import Principal
from app.core.config import Settings
from app.db.session import get_db_session
from app.main import create_app
from app.models.academics import (
    AcademicProgram,
    AcademicYear,
    ApprovedIntake,
    ProgramAcademicYear,
    SeatCategory,
)
from app.models.audit import AuditEvent
from app.models.enums import (
    AcademicYearStatus,
    EnrolmentStatus,
    InstitutionStatus,
    ProgramStatus,
    UserRole,
    UserStatus,
)
from app.models.identity import Enrolment
from app.models.ingestion import DataImportBatch
from app.models.institution import Institution
from app.models.user import User


def _seed_program(db, *, suffix: str, capacity: int):
    institution = Institution(
        aicte_code=f"SYNTH-{suffix}",
        name=f"Synthetic Institute {suffix}",
        state="Synthetic State",
        tier="Demo",
        status=InstitutionStatus.ACTIVE,
        is_synthetic=True,
    )
    db.add(institution)
    db.flush()
    year = AcademicYear(
        code=f"TEST-{suffix}-2026",
        starts_on=date(2026, 1, 1),
        ends_on=date(2026, 12, 31),
        status=AcademicYearStatus.ACTIVE,
    )
    program = AcademicProgram(
        institution_id=institution.id,
        code=f"CSE-{suffix}",
        title="Synthetic Computer Science",
        status=ProgramStatus.ACTIVE,
    )
    category = SeatCategory(code=f"GEN-{suffix}", label="Synthetic configured pool", is_active=True)
    db.add_all([year, program, category])
    db.flush()
    program_year = ProgramAcademicYear(
        institution_id=institution.id,
        program_id=program.id,
        academic_year_id=year.id,
    )
    db.add(program_year)
    db.flush()
    db.add_all(
        [
            ApprovedIntake(
                program_academic_year_id=program_year.id,
                seat_category_id=category.id,
                approved_seats=capacity,
            ),
            ApprovedIntake(
                program_academic_year_id=program_year.id,
                seat_category_id=None,
                approved_seats=capacity,
            ),
        ]
    )
    user = User(
        email=f"operator-{suffix}@example.test",
        display_name="Synthetic Operator",
        role=UserRole.INSTITUTION_ADMIN,
        status=UserStatus.ACTIVE,
        institution_id=institution.id,
    )
    db.add(user)
    db.flush()
    return institution, user, program


def _csv(program_code: str, category_code: str, students: list[tuple[str, str, str]]) -> str:
    lines = [
        "student_ref,apaar_id,full_name,dob,program_code,enrollment_year,consent_granted,"
        "admission_date,seat_category_code,supernumerary_seat,nri_status,oci_status,"
        "foreign_national_status,admission_status"
    ]
    for student_ref, apaar, name in students:
        lines.append(
            f'{student_ref},{apaar},"{name}",2006-04-22,{program_code},2026,false,'
            f"2026-05-01,{category_code},false,false,false,false,ADMITTED"
        )
    return "\n".join(lines) + "\n"


@pytest.mark.usefixtures("postgres_engine")
def test_upload_idempotency_error_report_and_commit_are_persistent(
    postgres_engine, monkeypatch, caplog
) -> None:
    factory = sessionmaker(bind=postgres_engine, autoflush=False, expire_on_commit=False)
    with factory() as db:
        institution, user, program = _seed_program(db, suffix="FLOW", capacity=2)
        db.commit()

    token = base64.urlsafe_b64encode(b"synthetic-test-ingestion-key-32b").decode().rstrip("=")
    settings = Settings(
        app_env="test",
        apaar_hmac_key=token,
        apaar_hmac_key_version="test-v1",
    )
    monkeypatch.setattr("app.services.ingestion.get_settings", lambda: settings)
    app = create_app(settings)
    principal = Principal(user.id, UserRole.INSTITUTION_ADMIN, institution.id)
    app.dependency_overrides[get_current_principal] = lambda: principal

    def db_dependency():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = db_dependency
    client = TestClient(app)
    content = _csv(
        program.code,
        "GEN-FLOW",
        [
            ("SYN-FLOW-1", "648291038472", 'Synthetic, "Quoted" Student'),
            ("SYN-FLOW-2", "", "Synthetic Provisional Student"),
        ],
    )
    request = {
        "institution_id": "caller-cannot-select-tenant",
        "actor_role": "regulator_admin",
        "actor_email": "untrusted@example.test",
        "filename": "synthetic-first.csv",
        "csv_content": content,
    }
    first = client.post("/api/v1/students/batches/upload", json=request)
    assert first.status_code == 201, first.text
    first_body = first.json()
    assert first_body["batch"]["institution_id"] == str(institution.id)
    assert len(first_body["records"]) == 2
    assert first_body["records"][0]["apaar_masked"] == "****-****-8472"
    assert "APAAR_FORMAT_VALID" in {
        finding["rule_code"] for finding in first_body["records"][0]["validation_results"]
    }
    assert first_body["records"][1]["row_status"] == "WARNING"
    assert "APAAR_NOT_PROVIDED" in {
        finding["rule_code"] for finding in first_body["records"][1]["validation_results"]
    }
    assert "CONSENT_NOT_CONFIRMED" in {
        finding["rule_code"] for finding in first_body["records"][1]["validation_results"]
    }
    assert "648291038472" not in first.text
    assert "apaar_hash" not in first.text

    retry = dict(request, filename="different-name.csv")
    second = client.post("/api/v1/students/batches/upload", json=retry)
    assert second.status_code == 200
    assert second.json()["batch"]["id"] == first_body["batch"]["id"]
    assert second.json()["idempotent_replay"] is True
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(DataImportBatch)) == 1
        assert db.scalar(select(func.count()).select_from(AuditEvent)) == 1

    details = client.get(f"/api/v1/students/batches/{first_body['batch']['id']}")
    assert details.status_code == 200
    assert details.json()["batch"]["total_rows"] == 2
    results = client.get("/api/v1/students/validation-results")
    assert len(results.json()["students"]) == 2

    repeated_student_ref = client.post(
        "/api/v1/students/batches/upload",
        json={
            "filename": "synthetic-duplicate.csv",
            "csv_content": _csv(
                program.code,
                "GEN-FLOW",
                [
                    ("SYN-DUPLICATE", "648291038472", "Synthetic Duplicate First"),
                    ("SYN-DUPLICATE", "748291038472", "Synthetic Duplicate Second"),
                ],
            ),
        },
    )
    assert repeated_student_ref.status_code == 201
    duplicate_records = repeated_student_ref.json()["records"]
    for record in duplicate_records:
        assert record["row_status"] == "REJECTED"
        assert "DUPLICATE_ENROLMENT_KEY_IN_BATCH" in {
            finding["rule_code"] for finding in record["validation_results"]
        }

    duplicate_apaar = client.post(
        "/api/v1/students/batches/upload",
        json={
            "filename": "synthetic-duplicate-apaar.csv",
            "csv_content": _csv(
                program.code,
                "GEN-FLOW",
                [
                    ("SYN-APAAR-A", "648291038472", "Synthetic APAAR A"),
                    ("SYN-APAAR-B", "648291038472", "Synthetic APAAR B"),
                ],
            ),
        },
    )
    assert duplicate_apaar.status_code == 201
    for record in duplicate_apaar.json()["records"]:
        assert record["row_status"] == "REVIEW_REQUIRED"
        assert "APAAR_DUPLICATE_IN_BATCH" in {
            finding["rule_code"] for finding in record["validation_results"]
        }

    invalid_fields_csv = _csv(
        "UNKNOWN-PROGRAM", "GEN-FLOW", [("SYN-INVALID", "invalid", "Synthetic Invalid Fields")]
    ).replace(",2026,", ",2099,")
    invalid_fields = client.post(
        "/api/v1/students/batches/upload",
        json={"filename": "synthetic-invalid.csv", "csv_content": invalid_fields_csv},
    )
    assert invalid_fields.status_code == 201
    invalid_findings = {
        finding["rule_code"]
        for finding in invalid_fields.json()["records"][0]["validation_results"]
    }
    assert {"APAAR_FORMAT_INVALID", "PROGRAM_UNKNOWN", "ACADEMIC_YEAR_UNMAPPED"} <= invalid_findings

    committed = client.post(f"/api/v1/students/batches/{first_body['batch']['id']}/commit")
    assert committed.status_code == 200, committed.text
    assert committed.json()["newly_committed"] == 2
    repeated_commit = client.post(f"/api/v1/students/batches/{first_body['batch']['id']}/commit")
    assert repeated_commit.status_code == 200
    assert repeated_commit.json()["newly_committed"] == 0
    replay_committed = client.post("/api/v1/students/batches/upload", json=request)
    assert replay_committed.status_code == 200
    assert replay_committed.json()["idempotent_replay"] is True
    assert replay_committed.json()["batch"]["committed"] is True
    assert replay_committed.json()["batch"]["committed_rows"] == 2
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Enrolment)) == 2
        assert db.scalar(select(func.count()).select_from(AuditEvent)) == 5

    unsafe_ref_content = _csv(program.code, "GEN-FLOW", [("=1+1", "", "Synthetic Invalid Ref")])
    unsafe = client.post(
        "/api/v1/students/batches/upload",
        json={"filename": "unsafe.csv", "csv_content": unsafe_ref_content},
    )
    assert unsafe.status_code == 201
    report = client.get(f"/api/v1/students/batches/{unsafe.json()['batch']['id']}/error-report")
    assert report.status_code == 200
    assert "'=1+1" in report.text
    assert "648291038472" not in caplog.text


def test_concurrent_batch_commits_do_not_overbook_capacity(postgres_engine, monkeypatch) -> None:
    factory = sessionmaker(bind=postgres_engine, autoflush=False, expire_on_commit=False)
    with factory() as db:
        institution, user, program = _seed_program(db, suffix="RACE", capacity=1)
        db.commit()
    token = base64.urlsafe_b64encode(b"synthetic-test-ingestion-key-32b").decode().rstrip("=")
    settings = Settings(
        app_env="test",
        apaar_hmac_key=token,
        apaar_hmac_key_version="test-v1",
    )
    monkeypatch.setattr("app.services.ingestion.get_settings", lambda: settings)
    app = create_app(settings)
    app.dependency_overrides[get_current_principal] = lambda: Principal(
        user.id, UserRole.INSTITUTION_ADMIN, institution.id
    )

    def db_dependency():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = db_dependency
    client = TestClient(app)
    batch_ids = []
    for suffix, apaar in (("A", "648291038472"), ("B", "748291038472")):
        uploaded = client.post(
            "/api/v1/students/batches/upload",
            json={
                "filename": f"race-{suffix}.csv",
                "csv_content": _csv(
                    program.code,
                    "GEN-RACE",
                    [(f"SYN-RACE-{suffix}", apaar, f"Synthetic Student {suffix}")],
                ),
            },
        )
        assert uploaded.status_code == 201, uploaded.text
        batch_ids.append(uploaded.json()["batch"]["id"])

    def commit(batch_id: str) -> int:
        return client.post(f"/api/v1/students/batches/{batch_id}/commit").status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(commit, batch_ids))
    assert sorted(statuses) == [200, 409]
    with factory() as db:
        committed_count = db.scalar(
            select(func.count())
            .select_from(Enrolment)
            .where(Enrolment.status == EnrolmentStatus.ACCEPTED)
        )
        assert committed_count == 1
