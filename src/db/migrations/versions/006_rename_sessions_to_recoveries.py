"""006 rename care episode sessions to recoveries

Revision ID: 006
Revises: 005
Create Date: 2026-06-11
"""

from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("DROP VIEW IF EXISTS care_episode_sessions_history"))
    op.execute(sa.text("ALTER TABLE care_episode_sessions RENAME TO care_episode_recoveries"))
    op.execute(sa.text("ALTER TABLE care_episode_sessions_audit RENAME TO care_episode_recoveries_audit"))
    op.execute(sa.text("ALTER TABLE care_episode_recoveries RENAME COLUMN session_id TO recovery_id"))
    op.execute(sa.text("ALTER TABLE care_episode_recoveries_audit RENAME COLUMN session_id TO recovery_id"))
    op.execute(
        sa.text(
            "ALTER INDEX ix_care_episode_sessions_tenant_uuid "
            "RENAME TO ix_care_episode_recoveries_tenant_uuid"
        )
    )
    op.execute(sa.text("SELECT audit.setup_views('public', 'care_episode_recoveries')"))


def downgrade() -> None:
    raise NotImplementedError("care episode migration is irreversible")
