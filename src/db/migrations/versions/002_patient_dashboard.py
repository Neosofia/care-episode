"""002 patient dashboard appointments and inbox messages

Revision ID: 002
Revises: 001
Create Date: 2026-06-02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "care_episode_appointments",
        sa.Column(
            "appointment_uuid",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("uuidv7()"),
        ),
        sa.Column("patient_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clinician_user_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clinician_display_name", sa.String(length=128), nullable=False),
        sa.Column("specialty", sa.String(length=128), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
    )
    op.create_index(
        "ix_care_episode_appointments_patient_uuid",
        "care_episode_appointments",
        ["patient_uuid"],
    )
    op.create_index(
        "ix_care_episode_appointments_scheduled_at",
        "care_episode_appointments",
        ["scheduled_at"],
    )

    op.create_table(
        "care_episode_inbox_messages",
        sa.Column(
            "message_uuid",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("uuidv7()"),
        ),
        sa.Column("patient_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_user_uuid", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sender_display_name", sa.String(length=128), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_care_episode_inbox_messages_patient_uuid",
        "care_episode_inbox_messages",
        ["patient_uuid"],
    )
    op.create_index(
        "ix_care_episode_inbox_messages_sent_at",
        "care_episode_inbox_messages",
        ["sent_at"],
    )

    op.execute(sa.text("SELECT audit.setup_tracking('public', 'care_episode_appointments')"))
    op.execute(sa.text("SELECT audit.setup_tracking('public', 'care_episode_inbox_messages')"))


def downgrade() -> None:
    raise NotImplementedError("care episode migration is irreversible")
