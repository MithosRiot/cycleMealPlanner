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


def _column_names(bind, table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    sqlite = bind.dialect.name == "sqlite"

    # Some older disposable/user databases were stamped beyond the planning
    # migrations while missing one or both columns. Repair that historical
    # schema drift before newer seed/UI code relies on them.
    cycle_columns = _column_names(bind, "meal_cycles")
    if "population_rules" not in cycle_columns:
        op.add_column(
            "meal_cycles",
            sa.Column("population_rules", sa.Text(), nullable=False, server_default="{}"),
        )
    if "smart_preferences" not in cycle_columns:
        op.add_column(
            "meal_cycles",
            sa.Column("smart_preferences", sa.Text(), nullable=False, server_default="{}"),
        )

    # SQLite batch_alter_table recreates the ingredients table. Because many
    # existing tables reference ingredients and foreign_keys=ON is intentional,
    # dropping that temporary source table fails on populated databases. These
    # columns can be added in-place safely. Check first so a partially attempted
    # non-transactional SQLite migration can also be retried safely.
    ingredient_columns = _column_names(bind, "ingredients")
    if "staple_enabled" not in ingredient_columns:
        op.add_column(
            "ingredients",
            sa.Column("staple_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if "staple_minimum" not in ingredient_columns:
        op.add_column("ingredients", sa.Column("staple_minimum", sa.Numeric(14, 6), nullable=True))
    if "staple_target" not in ingredient_columns:
        op.add_column("ingredients", sa.Column("staple_target", sa.Numeric(14, 6), nullable=True))
    if "staple_unit_id" not in ingredient_columns:
        if sqlite:
            # Alembic normally emits the FK as a second ALTER TABLE statement,
            # which SQLite cannot do. SQLite can add the nullable REFERENCES
            # clause atomically as part of ADD COLUMN.
            op.execute(
                "ALTER TABLE ingredients ADD COLUMN staple_unit_id INTEGER "
                "REFERENCES measurement_units(id) ON DELETE SET NULL"
            )
        else:
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
        existing_checks = {item["name"] for item in sa.inspect(bind).get_check_constraints("ingredients")}
        if "ck_ingredients_staple_minimum_nonnegative" not in existing_checks:
            op.create_check_constraint(
                "ck_ingredients_staple_minimum_nonnegative",
                "ingredients",
                "staple_minimum IS NULL OR staple_minimum >= 0",
            )
        if "ck_ingredients_staple_target_nonnegative" not in existing_checks:
            op.create_check_constraint(
                "ck_ingredients_staple_target_nonnegative",
                "ingredients",
                "staple_target IS NULL OR staple_target >= 0",
            )
        if "ck_ingredients_staple_target_gte_minimum" not in existing_checks:
            op.create_check_constraint(
                "ck_ingredients_staple_target_gte_minimum",
                "ingredients",
                "staple_minimum IS NULL OR staple_target IS NULL OR staple_target >= staple_minimum",
            )


def downgrade() -> None:
    bind = op.get_bind()
    sqlite = bind.dialect.name == "sqlite"

    if not sqlite:
        existing_checks = {item["name"] for item in sa.inspect(bind).get_check_constraints("ingredients")}
        for constraint_name in (
            "ck_ingredients_staple_target_gte_minimum",
            "ck_ingredients_staple_target_nonnegative",
            "ck_ingredients_staple_minimum_nonnegative",
        ):
            if constraint_name in existing_checks:
                op.drop_constraint(constraint_name, "ingredients", type_="check")

    ingredient_columns = _column_names(bind, "ingredients")
    for column_name in ("staple_unit_id", "staple_target", "staple_minimum", "staple_enabled"):
        if column_name in ingredient_columns:
            op.drop_column("ingredients", column_name)

    # population_rules/smart_preferences belong to earlier revisions and are
    # intentionally preserved on downgrade of this migration.
