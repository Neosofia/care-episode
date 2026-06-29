"""013 roster query indexes

Revision ID: 013
Revises: 012
Create Date: 2026-06-29
"""

from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_care_episode_recoveries_tenant_status",
        "care_episode_recoveries",
        ["tenant_uuid", "status"],
    )
    op.create_index(
        "ix_care_episode_recoveries_tenant_changed_at",
        "care_episode_recoveries",
        ["tenant_uuid", "changed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_care_episode_recoveries_tenant_changed_at", table_name="care_episode_recoveries")
    op.drop_index("ix_care_episode_recoveries_tenant_status", table_name="care_episode_recoveries")
