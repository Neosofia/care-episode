"""012 drop denormalized patient labels from recoveries

Revision ID: 012
Revises: 011
Create Date: 2026-06-17

User registry owns display_code and name; care episodes store patient_uuid only.
"""

from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text("DROP VIEW IF EXISTS public.care_episode_recoveries_history CASCADE")
    )
    op.execute(
        sa.text(
            "ALTER TABLE care_episode_recoveries "
            "DROP COLUMN IF EXISTS display_name, "
            "DROP COLUMN IF EXISTS display_code"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE care_episode_recoveries_audit "
            "DROP COLUMN IF EXISTS display_name, "
            "DROP COLUMN IF EXISTS display_code"
        )
    )
    op.execute(sa.text("SELECT audit.setup_views('public', 'care_episode_recoveries')"))


def downgrade() -> None:
    raise NotImplementedError("care episode migration is irreversible")
