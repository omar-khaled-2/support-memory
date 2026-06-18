"""Initial memory schema.

Revision ID: 9c5e7c1f3b2a
Revises:
Create Date: 2026-06-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9c5e7c1f3b2a"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "facts",
        sa.Column("fact_id", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("attribute", sa.String(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("source_event_id", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("fact_id"),
    )
    op.create_index("ix_facts_entity_type", "facts", ["entity_type"])
    op.create_index("ix_facts_entity_id", "facts", ["entity_id"])
    op.create_index("ix_facts_attribute", "facts", ["attribute"])

    op.create_table(
        "conflicts",
        sa.Column("conflict_id", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("attribute", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("conflict_id"),
    )
    op.create_index("ix_conflicts_entity_type", "conflicts", ["entity_type"])
    op.create_index("ix_conflicts_entity_id", "conflicts", ["entity_id"])
    op.create_index("ix_conflicts_attribute", "conflicts", ["attribute"])

    op.create_table(
        "snapshots",
        sa.Column("snapshot_id", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("context_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("snapshot_id"),
    )
    op.create_index("ix_snapshots_entity_id", "snapshots", ["entity_id"])


def downgrade() -> None:
    op.drop_table("snapshots")
    op.drop_table("conflicts")
    op.drop_table("facts")
