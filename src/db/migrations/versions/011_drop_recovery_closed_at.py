"""011 drop redundant closed_at from recoveries

Revision ID: 011
Revises: 010
Create Date: 2026-06-17

Closure time is derived at read time from changed_at when status is closed
(audit trigger maintains changed_at on every lifecycle update).
"""

from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("DROP VIEW IF EXISTS care_episode_recoveries_history"))
    op.drop_column("care_episode_recoveries", "closed_at")
    op.execute(
        sa.text(
            "ALTER TABLE care_episode_recoveries_audit "
            "DROP COLUMN IF EXISTS closed_at"
        )
    )
    op.execute(sa.text("SELECT audit.setup_views('public', 'care_episode_recoveries')"))


def downgrade() -> None:
    raise NotImplementedError("care episode migration is irreversible")
