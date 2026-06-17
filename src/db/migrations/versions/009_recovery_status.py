"""009 care episode lifecycle and multi-episode model

Revision ID: 009
Revises: 008
Create Date: 2026-06-17
"""

from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("DROP VIEW IF EXISTS care_episode_recoveries_history"))

    op.add_column(
        "care_episode_recoveries",
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
    )
    op.add_column(
        "care_episode_recoveries",
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "care_episode_recoveries",
        sa.Column("episode_uuid", sa.Uuid(), nullable=True),
    )
    op.execute(sa.text("UPDATE care_episode_recoveries SET episode_uuid = uuidv7() WHERE episode_uuid IS NULL"))
    op.alter_column("care_episode_recoveries", "episode_uuid", nullable=False)

    op.execute(sa.text("ALTER TABLE care_episode_recoveries DROP CONSTRAINT IF EXISTS care_episode_recoveries_pkey"))
    op.execute(sa.text("ALTER TABLE care_episode_recoveries DROP CONSTRAINT IF EXISTS care_episode_sessions_pkey"))
    op.create_primary_key(
        "care_episode_recoveries_pkey",
        "care_episode_recoveries",
        ["episode_uuid"],
    )
    op.create_index(
        "ix_care_episode_recoveries_patient_uuid",
        "care_episode_recoveries",
        ["patient_uuid"],
    )
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX uq_care_episode_recoveries_active_patient "
            "ON care_episode_recoveries (patient_uuid) "
            "WHERE status = 'active'"
        )
    )

    op.execute(
        sa.text(
            "UPDATE care_episode_recoveries_audit AS audit "
            "SET episode_uuid = recovery.episode_uuid "
            "FROM care_episode_recoveries AS recovery "
            "WHERE audit.patient_uuid = recovery.patient_uuid "
            "AND audit.episode_uuid IS NULL"
        )
    )
    op.execute(sa.text("SELECT audit.setup_views('public', 'care_episode_recoveries')"))


def downgrade() -> None:
    raise NotImplementedError("care episode migration is irreversible")
