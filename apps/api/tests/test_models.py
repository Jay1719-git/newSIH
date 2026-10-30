import uuid

import pytest
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.exc import IntegrityError

from app import models  # noqa: F401
from app.db.base import Base


def test_expected_relational_tables_and_key_constraints_exist() -> None:
    expected = {
        "institutions",
        "users",
        "academic_programs",
        "academic_years",
        "program_academic_years",
        "approved_intakes",
        "seat_categories",
        "student_identity_references",
        "enrolments",
        "data_import_batches",
        "import_batch_rows",
        "validation_findings",
        "review_cases",
        "consent_records",
        "audit_events",
    }
    assert expected <= set(Base.metadata.tables)
    assert "aadhaar" not in " ".join(Base.metadata.tables).lower()

    identity = Base.metadata.tables["student_identity_references"]
    assert "hmac_digest" in identity.c
    assert "apaar_id" not in identity.c
    assert any(isinstance(item, CheckConstraint) for item in identity.constraints)

    program_year = Base.metadata.tables["program_academic_years"]
    assert any(isinstance(item, ForeignKeyConstraint) for item in program_year.constraints)
    assert any(isinstance(item, UniqueConstraint) for item in program_year.constraints)


def test_postgres_migration_creates_schema(postgres_engine) -> None:
    from sqlalchemy import inspect

    assert set(Base.metadata.tables) <= set(inspect(postgres_engine).get_table_names())


def test_postgres_identity_digest_is_unique(postgres_engine) -> None:
    table = Base.metadata.tables["student_identity_references"]
    values = {
        "id": uuid.uuid4(),
        "key_version": "demo-v1",
        "hmac_digest": "a" * 64,
        "masked_apaar": "****-****-1234",
    }
    with postgres_engine.begin() as connection:
        connection.execute(table.insert().values(**values))

    with pytest.raises(IntegrityError):
        with postgres_engine.begin() as connection:
            connection.execute(table.insert().values(**{**values, "id": uuid.uuid4()}))
