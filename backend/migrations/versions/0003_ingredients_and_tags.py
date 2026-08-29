"""ingredients and tags

Revision ID: 0003_ingredients_and_tags
Revises: 0002_core_reference_data
Create Date: 2026-08-29
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0003_ingredients_and_tags"
down_revision: str | None = "0002_core_reference_data"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ingredients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("normalized_name", sa.String(length=120), nullable=False),
        sa.Column("shopping_category_id", sa.Integer(), nullable=True),
        sa.Column("preferred_unit_id", sa.Integer(), nullable=True),
        sa.Column("default_location_id", sa.Integer(), nullable=True),
        sa.Column("perishable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shopping_category_id"], ["shopping_categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["preferred_unit_id"], ["measurement_units.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["default_location_id"], ["inventory_locations.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("household_id", "normalized_name", name="uq_ingredients_household_normalized_name"),
    )

    op.create_table(
        "ingredient_aliases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ingredient_id", sa.Integer(), nullable=False),
        sa.Column("alias", sa.String(length=120), nullable=False),
        sa.Column("normalized_alias", sa.String(length=120), nullable=False),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("ingredient_id", "normalized_alias", name="uq_ingredient_alias_normalized"),
    )
    op.create_index("ix_ingredient_aliases_normalized_alias", "ingredient_aliases", ["normalized_alias"])

    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("normalized_name", sa.String(length=80), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False, server_default="CUSTOM"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("household_id", "normalized_name", name="uq_tags_household_normalized_name"),
    )


def downgrade() -> None:
    op.drop_table("tags")
    op.drop_index("ix_ingredient_aliases_normalized_alias", table_name="ingredient_aliases")
    op.drop_table("ingredient_aliases")
    op.drop_table("ingredients")
