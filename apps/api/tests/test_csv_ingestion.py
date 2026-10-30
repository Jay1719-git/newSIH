from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_principal
from app.auth.policies import Principal
from app.db.session import get_db_session
from app.main import create_app
from app.models.enums import UserRole
from app.services.csv_ingestion import (
    CsvStructureError,
    parse_csv_content,
    spreadsheet_safe,
)


def test_csv_parser_supports_quoted_commas_quotes_and_newlines() -> None:
    parsed = parse_csv_content(
        "student_ref,apaar_id,full_name,dob,program_code,enrollment_year,consent_granted\n"
        'SYN-1,,"Example, Student",2006-01-02,CSE,2026,true\n'
    )
    assert parsed.rows[0][1]["full_name"] == "Example, Student"

    multiline = parse_csv_content(
        "student_ref,apaar_id,full_name,dob,program_code,enrollment_year,consent_granted\n"
        'SYN-2,,"Example ""Quoted""\nStudent",2006-01-02,CSE,2026,true\n'
    )
    assert multiline.rows[0][1]["full_name"] == 'Example "Quoted"\nStudent'


def test_csv_parser_distinguishes_structural_errors_and_refuses_aadhaar() -> None:
    with pytest.raises(CsvStructureError, match="missing"):
        parse_csv_content("student_ref,full_name\nSYN-1,Example\n")
    with pytest.raises(CsvStructureError, match="Aadhaar"):
        parse_csv_content(
            "student_ref,apaar_id,aadhaar_no,full_name,dob,program_code,enrollment_year,consent_granted\n"
            "SYN-1,,123,Example,2006-01-01,CSE,2026,true\n"
        )
    with pytest.raises(CsvStructureError, match="malformed"):
        parse_csv_content(
            "student_ref,apaar_id,full_name,dob,program_code,enrollment_year,consent_granted\n"
            'SYN-1,,"unclosed,2006-01-01,CSE,2026,true\n'
        )


def test_csv_parser_rejects_inconsistent_field_counts_and_limits(monkeypatch) -> None:
    with pytest.raises(CsvStructureError, match="inconsistent"):
        parse_csv_content(
            "student_ref,apaar_id,full_name,dob,program_code,enrollment_year,consent_granted\n"
            "SYN-1,,Example,2006-01-01,CSE,2026,true,extra\n"
        )
    monkeypatch.setattr("app.services.csv_ingestion.MAX_CSV_ROWS", 1)
    with pytest.raises(CsvStructureError, match="row count"):
        parse_csv_content(
            "student_ref,apaar_id,full_name,dob,program_code,enrollment_year,consent_granted\n"
            "SYN-1,,Example,2006-01-01,CSE,2026,true\n"
            "SYN-2,,Example,2006-01-01,CSE,2026,true\n"
        )


def test_csv_export_cells_are_safe_for_spreadsheet_formulas() -> None:
    assert spreadsheet_safe("=1+1").startswith("'=")
    assert spreadsheet_safe("student-1") == "student-1"


def test_malformed_upload_has_structural_error_envelope_without_database() -> None:
    app = create_app()
    principal = Principal(uuid.uuid4(), UserRole.INSTITUTION_OPERATOR, uuid.uuid4())
    app.dependency_overrides[get_current_principal] = lambda: principal

    def no_db():
        yield None

    app.dependency_overrides[get_db_session] = no_db
    response = TestClient(app).post(
        "/api/v1/students/batches/upload",
        json={"filename": "synthetic.csv", "csv_content": "not,a,valid,contract\n"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "MALFORMED_CSV"
    assert response.json()["error"]["request_id"]
