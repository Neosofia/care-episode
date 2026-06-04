"""004 care episode session last_activity

Revision ID: 004
Revises: 003
Create Date: 2026-06-04
"""

from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("DROP VIEW IF EXISTS care_episode_sessions_history"))
    op.execute(
        sa.text(
            """
            ALTER TABLE care_episode_sessions
            ADD COLUMN IF NOT EXISTS last_activity VARCHAR(64)
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE care_episode_sessions
            SET last_activity = to_char(changed_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
            WHERE last_activity IS NULL
            """
        )
    )
    op.alter_column(
        "care_episode_sessions",
        "last_activity",
        existing_type=sa.String(length=64),
        nullable=False,
    )
    op.execute(sa.text("SELECT audit.setup_views('public', 'care_episode_sessions')"))


def downgrade() -> None:
    raise NotImplementedError("care episode migration is irreversible")
