"""003 replace featured with risk_level on care episode sessions

Revision ID: 003
Revises: 002
Create Date: 2026-06-02
"""

from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # History view unions main + _audit columns; drop before column surgery.
    # ADD COLUMN on the main table re-enrolls via audit DDL triggers and recreates the view.
    op.execute(sa.text("DROP VIEW IF EXISTS care_episode_sessions_history"))
    op.add_column(
        "care_episode_sessions",
        sa.Column("risk_level", sa.String(length=16)),
    )
    op.execute(sa.text("DROP VIEW IF EXISTS care_episode_sessions_history"))
    op.execute(sa.text("ALTER TABLE care_episode_sessions_audit DROP COLUMN IF EXISTS featured"))
    op.drop_column("care_episode_sessions", "featured")
    op.execute(sa.text("SELECT audit.setup_views('public', 'care_episode_sessions')"))


def downgrade() -> None:
    raise NotImplementedError("care episode migration is irreversible")
