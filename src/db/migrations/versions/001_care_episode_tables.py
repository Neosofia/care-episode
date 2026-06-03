"""001 care episode tables

Revision ID: 001
Revises: 000
Create Date: 2026-06-02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = "000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "care_episode_sessions",
        sa.Column("patient_uuid", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("display_code", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("surgery", sa.String(length=255), nullable=False),
        sa.Column("procedure_date", sa.Date(), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("featured", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("tenant_uuid", postgresql.UUID(as_uuid=True), nullable=False),
    )
    op.create_index("ix_care_episode_sessions_tenant_uuid", "care_episode_sessions", ["tenant_uuid"])

    op.create_table(
        "care_episode_records",
        sa.Column("record_uuid", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("uuidv7()")),
        sa.Column("patient_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("date", sa.String(length=32), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("image_key", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_care_episode_records_patient_uuid", "care_episode_records", ["patient_uuid"])

    op.create_table(
        "care_episode_transcripts",
        sa.Column("message_uuid", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("uuidv7()")),
        sa.Column("patient_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("time_label", sa.String(length=32), nullable=False),
    )
    op.create_index("ix_care_episode_transcripts_patient_uuid", "care_episode_transcripts", ["patient_uuid"])

    op.execute(sa.text("SELECT audit.setup_tracking('public', 'care_episode_sessions')"))
    op.execute(sa.text("SELECT audit.setup_tracking('public', 'care_episode_records')"))
    op.execute(sa.text("SELECT audit.setup_tracking('public', 'care_episode_transcripts')"))


def downgrade() -> None:
    raise NotImplementedError("care episode migration is irreversible")
