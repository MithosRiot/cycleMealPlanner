"""recipe ingredient substitutions

Revision ID: 0017_recipe_substitutions
Revises: 0016_recipe_equipment
Create Date: 2026-08-30
"""

from alembic import op
import sqlalchemy as sa

revision = "0017_recipe_substitutions"
down_revision = "0016_recipe_equipment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recipe_ingredient_substitutions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recipe_ingredient_id", sa.Integer(), nullable=False),
        sa.Column("substitute_ingredient_id", sa.Integer(), nullable=False),
        sa.Column("ratio", sa.Numeric(14, 6), nullable=False, server_default="1"),
        sa.Column("preferred", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("ratio > 0", name="ck_recipe_ingredient_substitutions_ratio_positive"),
        sa.CheckConstraint("sort_order >= 0", name="ck_recipe_ingredient_substitutions_sort_order_nonnegative"),
        sa.ForeignKeyConstraint(["recipe_ingredient_id"], ["recipe_ingredients.id"], ondelete="CASCADE", name="fk_recipe_ingredient_substitutions_recipe_ingredient"),
        sa.ForeignKeyConstraint(["substitute_ingredient_id"], ["ingredients.id"], ondelete="RESTRICT", name="fk_recipe_ingredient_substitutions_substitute_ingredient"),
        sa.UniqueConstraint("recipe_ingredient_id", "substitute_ingredient_id", name="uq_recipe_ingredient_substitutions_alternate"),
    )


def downgrade() -> None:
    op.drop_table("recipe_ingredient_substitutions")
