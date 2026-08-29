"""add meal cycles and slots

Revision ID: 0007_meal_cycles
Revises: 0006_saved_meals
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_meal_cycles"
down_revision = "0006_saved_meals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meal_cycles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("household_id", sa.Integer(), sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("normalized_name", sa.String(length=160), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("household_id", "normalized_name", name="uq_meal_cycles_household_normalized_name"),
        sa.CheckConstraint("duration_days > 0 AND duration_days <= 365", name="ck_meal_cycles_duration_supported"),
        sa.CheckConstraint("status IN ('DRAFT')", name="ck_meal_cycles_status"),
    )
    op.create_table(
        "meal_slot_definitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cycle_id", sa.Integer(), sa.ForeignKey("meal_cycles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.UniqueConstraint("cycle_id", "sort_order", name="uq_meal_slot_definitions_cycle_sort"),
        sa.CheckConstraint("sort_order >= 0", name="ck_meal_slot_definitions_sort_nonnegative"),
    )
    op.create_table(
        "cycle_slots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cycle_id", sa.Integer(), sa.ForeignKey("meal_cycles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slot_definition_id", sa.Integer(), sa.ForeignKey("meal_slot_definitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day_number", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.UniqueConstraint("cycle_id", "day_number", "slot_definition_id", name="uq_cycle_slots_day_definition"),
        sa.CheckConstraint("day_number > 0", name="ck_cycle_slots_day_positive"),
        sa.CheckConstraint("sort_order >= 0", name="ck_cycle_slots_sort_nonnegative"),
    )


def downgrade() -> None:
    op.drop_table("cycle_slots")
    op.drop_table("meal_slot_definitions")
    op.drop_table("meal_cycles")
