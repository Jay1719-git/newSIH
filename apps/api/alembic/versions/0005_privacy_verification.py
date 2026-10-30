"""Extend consent scope and track signed verification credential revocation.

Revision ID: 0005_privacy
Revises: 0004_duplicates
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_privacy"
down_revision = "0004_duplicates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("consent_records", sa.Column("verifier_user_id", sa.Uuid(), nullable=True))
    op.add_column("consent_records", sa.Column("permitted_claims", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("consent_records", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_consent_records_verifier_user_id_users", "consent_records", "users", ["verifier_user_id"], ["id"], ondelete="RESTRICT")
    op.add_column("external_verifier_grants", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "verification_credentials",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("jti", sa.String(64), nullable=False),
        sa.Column("verifier_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("enrolment_id", sa.Uuid(), sa.ForeignKey("enrolments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("uq_verification_credential_jti", "verification_credentials", ["jti"], unique=True)


def downgrade() -> None:
    op.drop_table("verification_credentials")
    op.drop_column("external_verifier_grants", "revoked_at")
    op.drop_constraint("fk_consent_records_verifier_user_id_users", "consent_records", type_="foreignkey")
    op.drop_column("consent_records", "expires_at")
    op.drop_column("consent_records", "permitted_claims")
    op.drop_column("consent_records", "verifier_user_id")
