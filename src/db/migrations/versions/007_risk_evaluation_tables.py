"""007 interaction rolling risk summary

Revision ID: 007
Revises: 006
Create Date: 2026-06-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interaction_risk_states",
        sa.Column("chat_interaction_uuid", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("patient_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index(
        "ix_interaction_risk_states_patient_uuid",
        "interaction_risk_states",
        ["patient_uuid"],
    )

    op.execute(sa.text("SELECT audit.setup_tracking('public', 'interaction_risk_states')"))


def downgrade() -> None:
    raise NotImplementedError("care episode migration is irreversible")
