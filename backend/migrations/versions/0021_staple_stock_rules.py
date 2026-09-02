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
    bind = op.get_bind()
    sqlite = bind.dialect.name == "sqlite"

    # SQLite batch_alter_table recreates the ingredients table. Because many
    # existing tables reference ingredients and foreign_keys=ON is intentional,
    # dropping that temporary source table fails on populated databases. These
    # four columns can be added in-place safely instead.
    op.add_column(
        "ingredients",
        sa.Column("staple_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("ingredients", sa.Column("staple_minimum", sa.Numeric(14, 6), nullable=True))
    op.add_column("ingredients", sa.Column("staple_target", sa.Numeric(14, 6), nullable=True))
    op.add_column(
        "ingredients",
        sa.Column(
            "staple_unit_id",
            sa.Integer(),
            sa.ForeignKey("measurement_units.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # SQLite cannot add table-level CHECK constraints without rebuilding the
    # referenced table. API validation remains authoritative there. Databases
    # that support ALTER TABLE constraints get the same DB-level guards as the
    # SQLAlchemy model.
    if not sqlite:
        op.create_check_constraint(
            "ck_ingredients_staple_minimum_nonnegative",
            "ingredients",
            "staple_minimum IS NULL OR staple_minimum >= 0",
        )
        op.create_check_constraint(
            "ck_ingredients_staple_target_nonnegative",
            "ingredients",
            "staple_target IS NULL OR staple_target >= 0",
        )
        op.create_check_constraint(
            "ck_ingredients_staple_target_gte_minimum",
            "ingredients",
            "staple_minimum IS NULL OR staple_target IS NULL OR staple_target >= staple_minimum",
        )


def downgrade() -> None:
    bind = op.get_bind()
    sqlite = bind.dialect.name == "sqlite"

    if not sqlite:
        op.drop_constraint("ck_ingredients_staple_target_gte_minimum", "ingredients", type_="check")
        op.drop_constraint("ck_ingredients_staple_target_nonnegative", "ingredients", type_="check")
        op.drop_constraint("ck_ingredients_staple_minimum_nonnegative", "ingredients", type_="check")

    # Modern SQLite supports DROP COLUMN. No batch table recreation is used, so
    # populated databases remain safe with foreign key enforcement enabled.
    op.drop_column("ingredients", "staple_unit_id")
    op.drop_column("ingredients", "staple_target")
    op.drop_column("ingredients", "staple_minimum")
    op.drop_column("ingredients", "staple_enabled")
