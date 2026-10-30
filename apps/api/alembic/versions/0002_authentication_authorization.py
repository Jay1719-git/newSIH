"""Add local authentication and identity/tenant authorization support.

Revision ID: 0002_auth
Revises: 0001_initial_schema
"""

from __future__ import annotations

from sqlalchemy import Column, String, Uuid, inspect

from alembic import context, op
from app import models  # noqa: F401
from app.db.base import Base

revision = "0002_auth"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if context.is_offline_mode():
        # The baseline revision creates the complete current metadata when rendered offline.
        return
    connection = op.get_bind()
    # Idempotent because the unreleased baseline metadata may already include these values.
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'student'")
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'external_verifier'")
    columns = {column["name"] for column in inspect(connection).get_columns("users")}
    if "password_hash" not in columns:
        op.add_column("users", Column("password_hash", String(256), nullable=True))
    if "student_identity_reference_id" not in columns:
        op.add_column("users", Column("student_identity_reference_id", Uuid(), nullable=True))
        op.create_foreign_key(
            "fk_users_student_identity_reference_id_student_identity_references",
            "users",
            "student_identity_references",
            ["student_identity_reference_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    indexes = {index["name"] for index in inspect(connection).get_indexes("users")}
    if "uq_users_student_identity_reference_id" not in indexes:
        op.create_index(
            "uq_users_student_identity_reference_id",
            "users",
            ["student_identity_reference_id"],
            unique=True,
        )
    for name in ("auth_sessions", "external_verifier_grants"):
        table = Base.metadata.tables[name]
        if name not in inspect(connection).get_table_names():
            table.create(connection)


def downgrade() -> None:
    if context.is_offline_mode():
        return
    connection = op.get_bind()
    tables = set(inspect(connection).get_table_names())
    if "external_verifier_grants" in tables:
        Base.metadata.tables["external_verifier_grants"].drop(connection)
    if "auth_sessions" in tables:
        Base.metadata.tables["auth_sessions"].drop(connection)
    indexes = {index["name"] for index in inspect(connection).get_indexes("users")}
    if "uq_users_student_identity_reference_id" in indexes:
        op.drop_index("uq_users_student_identity_reference_id", table_name="users")
    columns = {column["name"] for column in inspect(connection).get_columns("users")}
    if "student_identity_reference_id" in columns:
        op.drop_constraint(
            "fk_users_student_identity_reference_id_student_identity_references",
            "users",
            type_="foreignkey",
        )
        op.drop_column("users", "student_identity_reference_id")
    if "password_hash" in columns:
        op.drop_column("users", "password_hash")
    # PostgreSQL cannot remove values from an enum type; retain them on downgrade.
