"""criação inicial: schools, roles, users

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLE_NAME_ENUM = postgresql.ENUM(
    "direcao",
    "secretaria",
    "professor",
    "coordenacao_pedagogica",
    "responsavel",
    "aluno",
    "admin_tecnico",
    name="role_name",
)


def upgrade() -> None:
    op.create_table(
        "schools",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("slug", name="uq_schools_slug"),
    )

    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", ROLE_NAME_ENUM, nullable=False),
        sa.UniqueConstraint("name", name="uq_roles_name"),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=True),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_school_id", "users", ["school_id"])
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_schools_slug", "schools", ["slug"])


def downgrade() -> None:
    op.drop_index("ix_schools_slug", table_name="schools")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_school_id", table_name="users")
    op.drop_table("users")
    op.drop_table("roles")
    op.drop_table("schools")
    ROLE_NAME_ENUM.drop(op.get_bind(), checkfirst=True)
