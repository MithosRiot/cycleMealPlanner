"""staple stock rules

Revision ID: 0021_staple_stock_rules
Revises: 0020_inventory_reservations
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0021_staple_stock_rules"
down_revision: Union[str, None] = "0020_inventory_reservations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("ingredients") as batch_op:
        batch_op.add_column(sa.Column("staple_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("staple_minimum", sa.Numeric(14, 6), nullable=True))
        batch_op.add_column(sa.Column("staple_target", sa.Numeric(14, 6), nullable=True))
        batch_op.add_column(sa.Column("staple_unit_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_ingredients_staple_unit_id_measurement_units",
            "measurement_units",
            ["staple_unit_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_check_constraint(
            "ck_ingredients_staple_minimum_nonnegative",
            "staple_minimum IS NULL OR staple_minimum >= 0",
        )
        batch_op.create_check_constraint(
            "ck_ingredients_staple_target_nonnegative",
            "staple_target IS NULL OR staple_target >= 0",
        )
        batch_op.create_check_constraint(
            "ck_ingredients_staple_target_gte_minimum",
            "staple_minimum IS NULL OR staple_target IS NULL OR staple_target >= staple_minimum",
        )


def downgrade() -> None:
    with op.batch_alter_table("ingredients") as batch_op:
        batch_op.drop_constraint("ck_ingredients_staple_target_gte_minimum", type_="check")
        batch_op.drop_constraint("ck_ingredients_staple_target_nonnegative", type_="check")
        batch_op.drop_constraint("ck_ingredients_staple_minimum_nonnegative", type_="check")
        batch_op.drop_constraint("fk_ingredients_staple_unit_id_measurement_units", type_="foreignkey")
        batch_op.drop_column("staple_unit_id")
        batch_op.drop_column("staple_target")
        batch_op.drop_column("staple_minimum")
        batch_op.drop_column("staple_enabled")
