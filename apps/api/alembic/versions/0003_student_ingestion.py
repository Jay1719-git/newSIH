"""Persist deterministic student import rows and admission attributes.

Revision ID: 0003_ingestion
Revises: 0002_auth
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003_ingestion"
down_revision = "0002_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError("WEAVE student ingestion migration requires PostgreSQL")

    op.execute("ALTER TYPE finding_outcome ADD VALUE IF NOT EXISTS 'REVIEW'")
    row_status = postgresql.ENUM(
        "READY",
        "WARNING",
        "REVIEW_REQUIRED",
        "REJECTED",
        "COMMITTED",
        name="import_row_status",
        create_type=False,
    )
    row_status.create(bind, checkfirst=True)
    op.add_column(
        "data_import_batches",
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column("import_batch_rows", "student_ref", existing_type=sa.String(80), nullable=True)
    op.alter_column("import_batch_rows", "masked_apaar", existing_type=sa.String(16), nullable=True)
    op.alter_column("import_batch_rows", "full_name", existing_type=sa.String(200), nullable=True)
    op.alter_column(
        "import_batch_rows", "date_of_birth", existing_type=sa.String(10), nullable=True
    )
    op.alter_column(
        "import_batch_rows", "consent_granted", existing_type=sa.Boolean(), nullable=True
    )
    op.add_column("import_batch_rows", sa.Column("admission_date", sa.Date(), nullable=True))
    op.add_column(
        "import_batch_rows",
        sa.Column(
            "seat_category_id",
            sa.Uuid(),
            sa.ForeignKey("seat_categories.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.add_column(
        "import_batch_rows",
        sa.Column("supernumerary_seat", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "import_batch_rows",
        sa.Column("nri_status", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "import_batch_rows",
        sa.Column("oci_status", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "import_batch_rows",
        sa.Column(
            "foreign_national_status", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        "import_batch_rows",
        sa.Column("admission_status", sa.String(32), nullable=False, server_default="ADMITTED"),
    )
    op.add_column(
        "import_batch_rows",
        sa.Column("row_status", row_status, nullable=False, server_default="READY"),
    )
    op.alter_column("enrolments", "identity_reference_id", existing_type=sa.Uuid(), nullable=True)
    op.create_index(
        "uq_enrolment_tenant_program_student_active",
        "enrolments",
        ["institution_id", "program_academic_year_id", "student_ref"],
        unique=True,
        postgresql_where=sa.text("status != 'WITHDRAWN'"),
    )


def downgrade() -> None:
    op.drop_index("uq_enrolment_tenant_program_student_active", table_name="enrolments")
    op.alter_column("enrolments", "identity_reference_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_column("import_batch_rows", "row_status")
    op.drop_column("import_batch_rows", "admission_status")
    op.drop_column("import_batch_rows", "foreign_national_status")
    op.drop_column("import_batch_rows", "oci_status")
    op.drop_column("import_batch_rows", "nri_status")
    op.drop_column("import_batch_rows", "supernumerary_seat")
    op.drop_column("import_batch_rows", "seat_category_id")
    op.drop_column("import_batch_rows", "admission_date")
    op.drop_column("data_import_batches", "committed_at")
    postgresql.ENUM(name="import_row_status").drop(op.get_bind(), checkfirst=True)
