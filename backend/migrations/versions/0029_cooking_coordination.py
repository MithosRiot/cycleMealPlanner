"""add cooking coordination metadata

Revision ID: 0029_cooking_coordination
Revises: 0028_cooking_equipment_temperature
Create Date: 2026-09-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0029_cooking_coordination"
down_revision: Union[str, None] = "0028_cooking_equipment_temperature"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "recipe_cooking_coordination" not in tables:
        op.create_table(
            "recipe_cooking_coordination",
            sa.Column("cooking_step_id", sa.Integer(), sa.ForeignKey("recipe_cooking_steps.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("stage", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("parallel_capable", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.CheckConstraint("stage >= 0", name="ck_recipe_cooking_coordination_stage_nonnegative"),
        )
    if "recipe_cooking_dependencies" not in tables:
        op.create_table(
            "recipe_cooking_dependencies",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("cooking_step_id", sa.Integer(), sa.ForeignKey("recipe_cooking_steps.id", ondelete="CASCADE"), nullable=False),
            sa.Column("depends_on_step_id", sa.Integer(), sa.ForeignKey("recipe_cooking_steps.id", ondelete="CASCADE"), nullable=False),
            sa.UniqueConstraint("cooking_step_id", "depends_on_step_id", name="uq_recipe_cooking_dependency"),
            sa.CheckConstraint("cooking_step_id <> depends_on_step_id", name="ck_recipe_cooking_dependency_not_self"),
        )


def downgrade() -> None:
    op.drop_table("recipe_cooking_dependencies")
    op.drop_table("recipe_cooking_coordination")
