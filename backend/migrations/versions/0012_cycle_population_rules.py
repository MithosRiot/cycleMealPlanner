"""cycle population rules

Revision ID: 0012_cycle_population_rules
Revises: 0011_shopping_completion
Create Date: 2026-08-29
"""

from alembic import op
import sqlalchemy as sa

revision = "0012_cycle_population_rules"
down_revision = "0011_shopping_completion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("meal_cycles") as batch_op:
        batch_op.add_column(sa.Column("population_rules", sa.Text(), nullable=False, server_default="{}"))


def downgrade() -> None:
    with op.batch_alter_table("meal_cycles") as batch_op:
        batch_op.drop_column("population_rules")
