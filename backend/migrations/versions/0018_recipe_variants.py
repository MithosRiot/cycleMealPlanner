"""add recipe variants

Revision ID: 0018_recipe_variants
Revises: 0017_recipe_substitutions
"""
from alembic import op
import sqlalchemy as sa

revision = "0018_recipe_variants"
down_revision = "0017_recipe_substitutions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recipe_variants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recipe_id", sa.Integer(), sa.ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("normalized_name", sa.String(length=160), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("recipe_id", "normalized_name", name="uq_recipe_variants_recipe_normalized_name"),
        sa.CheckConstraint("sort_order >= 0", name="ck_recipe_variants_sort_order_nonnegative"),
    )
    op.create_table(
        "recipe_variant_ingredient_overrides",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("variant_id", sa.Integer(), sa.ForeignKey("recipe_variants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recipe_ingredient_id", sa.Integer(), sa.ForeignKey("recipe_ingredients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 6), nullable=True),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("measurement_units.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("substitution_id", sa.Integer(), sa.ForeignKey("recipe_ingredient_substitutions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("preparation", sa.String(length=160), nullable=True),
        sa.Column("prep_method", sa.String(length=80), nullable=True),
        sa.Column("prep_size", sa.String(length=80), nullable=True),
        sa.Column("prep_state", sa.String(length=80), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("variant_id", "recipe_ingredient_id", name="uq_recipe_variant_override_ingredient"),
        sa.CheckConstraint("quantity IS NULL OR quantity >= 0", name="ck_recipe_variant_override_quantity_nonnegative"),
    )


def downgrade() -> None:
    op.drop_table("recipe_variant_ingredient_overrides")
    op.drop_table("recipe_variants")
