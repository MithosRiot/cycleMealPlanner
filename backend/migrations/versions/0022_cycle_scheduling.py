"""cycle scheduling

Revision ID: 0022_cycle_scheduling
Revises: 0021_staple_stock_rules
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0022_cycle_scheduling"
down_revision: Union[str, None] = "0021_staple_stock_rules"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("meal_slot_definitions", sa.Column("serving_time", sa.Time(), nullable=True))


def downgrade() -> None:
    op.drop_column("meal_slot_definitions", "serving_time")
