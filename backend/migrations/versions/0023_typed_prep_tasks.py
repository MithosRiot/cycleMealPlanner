"""typed advance prep tasks

Revision ID: 0023_typed_prep_tasks
Revises: 0022_cycle_scheduling
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0023_typed_prep_tasks"
down_revision: Union[str, None] = "0022_cycle_scheduling"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("recipe_advance_prep")}
    if "task_type" not in columns:
        op.add_column(
            "recipe_advance_prep",
            sa.Column("task_type", sa.String(length=20), nullable=False, server_default="PREP"),
        )

    if bind.dialect.name != "sqlite":
        op.create_check_constraint(
            "ck_recipe_advance_prep_task_type",
            "recipe_advance_prep",
            "task_type IN ('PREP','THAW','MARINATE','SOAK','PROOF')",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.drop_constraint("ck_recipe_advance_prep_task_type", "recipe_advance_prep", type_="check")
    columns = {column["name"] for column in sa.inspect(bind).get_columns("recipe_advance_prep")}
    if "task_type" in columns:
        op.drop_column("recipe_advance_prep", "task_type")
