"""008 drop interaction risk idempotency columns

Revision ID: 008
Revises: 007
Create Date: 2026-06-12
"""

from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("DROP VIEW IF EXISTS interaction_risk_states_history"))
    op.execute(sa.text("DROP TABLE IF EXISTS interaction_risk_states_audit CASCADE"))
    op.execute(
        sa.text(
            "ALTER TABLE interaction_risk_states "
            "DROP COLUMN IF EXISTS last_evaluated_message_uuid, "
            "DROP COLUMN IF EXISTS last_evaluated_outcome, "
            "DROP COLUMN IF EXISTS last_escalated"
        )
    )
    op.execute(sa.text("SELECT audit.setup_tracking('public', 'interaction_risk_states')"))


def downgrade() -> None:
    raise NotImplementedError("care episode migration is irreversible")
