"""advance prep definitions

Revision ID: 0015_advance_prep_definitions
Revises: 0014_recipe_prep_groups
Create Date: 2026-08-30
"""

from alembic import op
import sqlalchemy as sa

revision = "0015_advance_prep_definitions"
down_revision = "0014_recipe_prep_groups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recipe_advance_prep",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("prep_group_id", sa.Integer()),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("lead_time_minutes", sa.Integer(), nullable=False),
        sa.Column("duration_minutes", sa.Integer()),
        sa.Column("instructions", sa.Text()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("lead_time_minutes >= 0", name="ck_recipe_advance_prep_lead_nonnegative"),
        sa.CheckConstraint("duration_minutes IS NULL OR duration_minutes >= 0", name="ck_recipe_advance_prep_duration_nonnegative"),
        sa.CheckConstraint("sort_order >= 0", name="ck_recipe_advance_prep_sort_order_nonnegative"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE", name="fk_recipe_advance_prep_recipe"),
        sa.ForeignKeyConstraint(["prep_group_id"], ["recipe_prep_groups.id"], ondelete="SET NULL", name="fk_recipe_advance_prep_prep_group"),
    )


def downgrade() -> None:
    op.drop_table("recipe_advance_prep")
