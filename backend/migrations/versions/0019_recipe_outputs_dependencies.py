"""recipe outputs and dependencies

Revision ID: 0019_recipe_outputs_dependencies
Revises: 0018_recipe_variants
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0019_recipe_outputs_dependencies"
down_revision: Union[str, None] = "0018_recipe_variants"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recipe_outputs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recipe_id", sa.Integer(), sa.ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("normalized_name", sa.String(length=160), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 6), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("measurement_units.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("recipe_id", "normalized_name", name="uq_recipe_outputs_recipe_normalized_name"),
        sa.CheckConstraint("quantity > 0", name="ck_recipe_outputs_quantity_positive"),
        sa.CheckConstraint("sort_order >= 0", name="ck_recipe_outputs_sort_order_nonnegative"),
    )
    op.create_table(
        "recipe_dependencies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recipe_id", sa.Integer(), sa.ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recipe_output_id", sa.Integer(), sa.ForeignKey("recipe_outputs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 6), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("measurement_units.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("scaling_mode", sa.String(length=20), nullable=False, server_default="LINEAR"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("recipe_id", "recipe_output_id", name="uq_recipe_dependencies_recipe_output"),
        sa.CheckConstraint("quantity > 0", name="ck_recipe_dependencies_quantity_positive"),
        sa.CheckConstraint("sort_order >= 0", name="ck_recipe_dependencies_sort_order_nonnegative"),
        sa.CheckConstraint("scaling_mode IN ('LINEAR','FIXED','ROUND_UP','MANUAL')", name="ck_recipe_dependencies_scaling_mode"),
    )


def downgrade() -> None:
    op.drop_table("recipe_dependencies")
    op.drop_table("recipe_outputs")
