"""comunicados: announcements, announcement_classrooms, announcement_reads

Revision ID: 0003_announcements
Revises: 0002_cadastros
Create Date: 2026-11-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_announcements"
down_revision: Union[str, None] = "0002_cadastros"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "announcements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("audience", sa.String(length=20), nullable=False),
        sa.Column("requires_confirmation", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("publish_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("audience IN ('school', 'classrooms')", name="ck_announcements_audience"),
    )
    op.create_index("ix_announcements_school_publish_at", "announcements", ["school_id", "publish_at"])
    op.create_index("ix_announcements_author_id", "announcements", ["author_id"])

    op.create_table(
        "announcement_classrooms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("announcement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("announcements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("classroom_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("announcement_id", "classroom_id", name="uq_announcement_classroom"),
    )
    op.create_index("ix_announcement_classrooms_announcement_id", "announcement_classrooms", ["announcement_id"])
    op.create_index("ix_announcement_classrooms_classroom_id", "announcement_classrooms", ["classroom_id"])

    op.create_table(
        "announcement_reads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("announcement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("announcements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("announcement_id", "user_id", name="uq_announcement_read_user"),
    )
    op.create_index("ix_announcement_reads_announcement_id", "announcement_reads", ["announcement_id"])
    op.create_index("ix_announcement_reads_user_id", "announcement_reads", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_announcement_reads_user_id", table_name="announcement_reads")
    op.drop_index("ix_announcement_reads_announcement_id", table_name="announcement_reads")
    op.drop_table("announcement_reads")

    op.drop_index("ix_announcement_classrooms_classroom_id", table_name="announcement_classrooms")
    op.drop_index("ix_announcement_classrooms_announcement_id", table_name="announcement_classrooms")
    op.drop_table("announcement_classrooms")

    op.drop_index("ix_announcements_author_id", table_name="announcements")
    op.drop_index("ix_announcements_school_publish_at", table_name="announcements")
    op.drop_table("announcements")
