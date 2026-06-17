"""010 care window days on recoveries

Revision ID: 010
Revises: 009
Create Date: 2026-06-17
"""

from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("DROP VIEW IF EXISTS care_episode_recoveries_history"))
    op.add_column(
        "care_episode_recoveries",
        sa.Column("care_window_days", sa.Integer(), nullable=False, server_default="30"),
    )
    op.execute(
        sa.text(
            "UPDATE care_episode_recoveries_audit AS audit "
            "SET care_window_days = recovery.care_window_days "
            "FROM care_episode_recoveries AS recovery "
            "WHERE audit.episode_uuid = recovery.episode_uuid "
            "AND audit.care_window_days IS NULL"
        )
    )
    op.execute(sa.text("SELECT audit.setup_views('public', 'care_episode_recoveries')"))


def downgrade() -> None:
    raise NotImplementedError("care episode migration is irreversible")
