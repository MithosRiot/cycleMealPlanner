"""recipe equipment

Revision ID: 0016_recipe_equipment
Revises: 0015_advance_prep_definitions
Create Date: 2026-08-30
"""

from alembic import op
import sqlalchemy as sa

revision = "0016_recipe_equipment"
down_revision = "0015_advance_prep_definitions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "equipment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("normalized_name", sa.String(length=160), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False, server_default="OTHER"),
        sa.Column("notes", sa.Text()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE", name="fk_equipment_household"),
        sa.UniqueConstraint("household_id", "normalized_name", name="uq_equipment_household_normalized_name"),
    )
    op.create_table(
        "recipe_equipment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("equipment_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("notes", sa.Text()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("quantity > 0", name="ck_recipe_equipment_quantity_positive"),
        sa.CheckConstraint("sort_order >= 0", name="ck_recipe_equipment_sort_order_nonnegative"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE", name="fk_recipe_equipment_recipe"),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.id"], ondelete="RESTRICT", name="fk_recipe_equipment_equipment"),
        sa.UniqueConstraint("recipe_id", "equipment_id", name="uq_recipe_equipment_recipe_equipment"),
    )


def downgrade() -> None:
    op.drop_table("recipe_equipment")
    op.drop_table("equipment")
