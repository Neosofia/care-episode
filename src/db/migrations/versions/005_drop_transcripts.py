"""005 drop care episode transcripts

Revision ID: 005
Revises: 004
Create Date: 2026-06-05
"""

from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("DROP VIEW IF EXISTS care_episode_transcripts_history"))
    op.drop_table("care_episode_transcripts_audit")
    op.drop_table("care_episode_transcripts")


def downgrade() -> None:
    raise NotImplementedError("care episode migration is irreversible")
