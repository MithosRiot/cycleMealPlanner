"""add planned meals

Revision ID: 0008_planned_meals
Revises: 0007_meal_cycles
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_planned_meals"
down_revision = "0007_meal_cycles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "planned_meals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cycle_slot_id", sa.Integer(), sa.ForeignKey("cycle_slots.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("meal_id", sa.Integer(), sa.ForeignKey("meals.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("locked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("snapshot_name", sa.String(length=160), nullable=False),
        sa.Column("snapshot_description", sa.Text(), nullable=True),
        sa.Column("snapshot_meal_types", sa.Text(), nullable=False),
        sa.Column("snapshot_components", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("planned_meals")
