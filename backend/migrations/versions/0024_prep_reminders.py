"""prep reminders

Revision ID: 0024_prep_reminders
Revises: 0023_typed_prep_tasks
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0024_prep_reminders"
down_revision: Union[str, None] = "0023_typed_prep_tasks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recipe_advance_prep",
        sa.Column("reminder_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "recipe_advance_prep",
        sa.Column("reminder_offset_minutes", sa.Integer(), nullable=True),
    )

    if op.get_bind().dialect.name != "sqlite":
        op.create_check_constraint(
            "ck_recipe_advance_prep_reminder_offset_nonnegative",
            "recipe_advance_prep",
            "reminder_offset_minutes IS NULL OR reminder_offset_minutes >= 0",
        )
        op.create_check_constraint(
            "ck_recipe_advance_prep_reminder_enabled_has_offset",
            "recipe_advance_prep",
            "reminder_enabled = false OR reminder_offset_minutes IS NOT NULL",
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint(
            "ck_recipe_advance_prep_reminder_enabled_has_offset",
            "recipe_advance_prep",
            type_="check",
        )
        op.drop_constraint(
            "ck_recipe_advance_prep_reminder_offset_nonnegative",
            "recipe_advance_prep",
            type_="check",
        )
    op.drop_column("recipe_advance_prep", "reminder_offset_minutes")
    op.drop_column("recipe_advance_prep", "reminder_enabled")
