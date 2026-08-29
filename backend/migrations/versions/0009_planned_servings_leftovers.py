"""planned servings and leftovers

Revision ID: 0009_planned_servings_leftovers
Revises: 0008_planned_meals
"""

from alembic import op
import sqlalchemy as sa

revision = "0009_planned_servings_leftovers"
down_revision = "0008_planned_meals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("planned_meals") as batch:
        batch.add_column(sa.Column("planned_servings", sa.Numeric(10, 3), nullable=False, server_default="4"))
        batch.add_column(sa.Column("planned_leftover_servings", sa.Numeric(10, 3), nullable=False, server_default="0"))
        batch.add_column(sa.Column("component_serving_overrides", sa.Text(), nullable=False, server_default="{}"))
        batch.add_column(sa.Column("scaled_components", sa.Text(), nullable=False, server_default="[]"))
        batch.create_check_constraint("ck_planned_meals_servings_positive", "planned_servings > 0")
        batch.create_check_constraint("ck_planned_meals_leftovers_nonnegative", "planned_leftover_servings >= 0")


def downgrade() -> None:
    with op.batch_alter_table("planned_meals") as batch:
        batch.drop_constraint("ck_planned_meals_leftovers_nonnegative", type_="check")
        batch.drop_constraint("ck_planned_meals_servings_positive", type_="check")
        batch.drop_column("scaled_components")
        batch.drop_column("component_serving_overrides")
        batch.drop_column("planned_leftover_servings")
        batch.drop_column("planned_servings")
