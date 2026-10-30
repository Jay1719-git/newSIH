"""Add private duplicate cases and human review history.

Revision ID: 0004_duplicates
Revises: 0003_ingestion
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0004_duplicates"
down_revision = "0003_ingestion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "student_identity_references",
        sa.Column(
            "normalization_version",
            sa.String(length=40),
            server_default="legacy-v0",
            nullable=False,
        ),
    )
    op.alter_column("student_identity_references", "normalization_version", server_default="identity-norm-v1")
    op.create_table(
        "duplicate_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("record_a_id", sa.Uuid(), nullable=False),
        sa.Column("record_b_id", sa.Uuid(), nullable=False),
        sa.Column("institution_a_id", sa.Uuid(), nullable=False),
        sa.Column("institution_b_id", sa.Uuid(), nullable=False),
        sa.Column("match_type", sa.String(length=48), nullable=False),
        sa.Column("confidence_band", sa.String(length=16), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=True),
        sa.Column("decision_history", sa.JSON(), nullable=False),
        sa.Column("scan_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("record_a_id < record_b_id", name="ck_duplicate_cases_canonical_record_pair"),
        sa.ForeignKeyConstraint(["institution_a_id"], ["institutions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["institution_b_id"], ["institutions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["record_a_id"], ["import_batch_rows.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["record_b_id"], ["import_batch_rows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_duplicate_case_record_pair", "duplicate_cases", ["record_a_id", "record_b_id"], unique=True)
    op.create_index("ix_duplicate_cases_a_status", "duplicate_cases", ["institution_a_id", "status"])
    op.create_index("ix_duplicate_cases_b_status", "duplicate_cases", ["institution_b_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_duplicate_cases_b_status", table_name="duplicate_cases")
    op.drop_index("ix_duplicate_cases_a_status", table_name="duplicate_cases")
    op.drop_index("uq_duplicate_case_record_pair", table_name="duplicate_cases")
    op.drop_table("duplicate_cases")
    op.drop_column("student_identity_references", "normalization_version")
