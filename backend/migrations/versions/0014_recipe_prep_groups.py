"""recipe prep groups and structured prep

Revision ID: 0014_recipe_prep_groups
Revises: 0013_smart_planning_preferences
Create Date: 2026-08-30
"""

from alembic import op
import sqlalchemy as sa

revision = "0014_recipe_prep_groups"
down_revision = "0013_smart_planning_preferences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recipe_prep_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("sort_order >= 0", name="ck_recipe_prep_groups_sort_order_nonnegative"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE", name="fk_recipe_prep_groups_recipe"),
    )
    with op.batch_alter_table("recipe_ingredients") as batch_op:
        batch_op.add_column(sa.Column("prep_group_id", sa.Integer()))
        batch_op.add_column(sa.Column("prep_method", sa.String(length=80)))
        batch_op.add_column(sa.Column("prep_size", sa.String(length=80)))
        batch_op.add_column(sa.Column("prep_state", sa.String(length=80)))
        batch_op.create_foreign_key("fk_recipe_ingredients_prep_group", "recipe_prep_groups", ["prep_group_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    with op.batch_alter_table("recipe_ingredients") as batch_op:
        batch_op.drop_constraint("fk_recipe_ingredients_prep_group", type_="foreignkey")
        batch_op.drop_column("prep_state")
        batch_op.drop_column("prep_size")
        batch_op.drop_column("prep_method")
        batch_op.drop_column("prep_group_id")
    op.drop_table("recipe_prep_groups")
