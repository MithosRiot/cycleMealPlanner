"""smart planning preferences

Revision ID: 0013_smart_planning_preferences
Revises: 0012_cycle_population_rules
Create Date: 2026-08-29
"""

from alembic import op
import sqlalchemy as sa

revision = "0013_smart_planning_preferences"
down_revision = "0012_cycle_population_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("meal_cycles") as batch_op:
        batch_op.add_column(sa.Column("smart_preferences", sa.Text(), nullable=False, server_default="{}"))


def downgrade() -> None:
    with op.batch_alter_table("meal_cycles") as batch_op:
        batch_op.drop_column("smart_preferences")
