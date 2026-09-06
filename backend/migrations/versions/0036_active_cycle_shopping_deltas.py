"""add active-cycle Shopping delta history

Revision ID: 0036_active_cycle_shopping_deltas
Revises: 0035_direct_recipe_occurrences
Create Date: 2026-09-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0036_active_cycle_shopping_deltas"
down_revision: Union[str, None] = "0035_direct_recipe_occurrences"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(bind, table_name: str) -> set[str]:
    return {row["name"] for row in sa.inspect(bind).get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    columns = _column_names(bind, "shopping_list_items")
    if "baseline_required_quantity" not in columns:
        op.add_column("shopping_list_items", sa.Column("baseline_required_quantity", sa.Numeric(16, 6), nullable=True))
    if "plan_delta_quantity" not in columns:
        op.add_column("shopping_list_items", sa.Column("plan_delta_quantity", sa.Numeric(16, 6), nullable=False, server_default="0"))
    if "purchased_excess_quantity" not in columns:
        op.add_column("shopping_list_items", sa.Column("purchased_excess_quantity", sa.Numeric(16, 6), nullable=False, server_default="0"))

    tables = set(sa.inspect(bind).get_table_names())
    if "shopping_item_purchases" not in tables:
        op.create_table(
            "shopping_item_purchases",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("shopping_list_item_id", sa.Integer(), sa.ForeignKey("shopping_list_items.id", ondelete="CASCADE"), nullable=False),
            sa.Column("actual_quantity", sa.Numeric(16, 6), nullable=False),
            sa.Column("actual_unit_id", sa.Integer(), sa.ForeignKey("measurement_units.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("purchase_date", sa.Date(), nullable=True),
            sa.Column("storage_location_id", sa.Integer(), sa.ForeignKey("inventory_locations.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("expiration_date", sa.Date(), nullable=True),
            sa.Column("purchase_notes", sa.Text(), nullable=True),
            sa.Column("inventory_lot_id", sa.Integer(), sa.ForeignKey("inventory_lots.id", ondelete="RESTRICT"), nullable=False, unique=True),
            sa.Column("completed_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_shopping_item_purchases_item", "shopping_item_purchases", ["shopping_list_item_id"])

    if "planned_meal_revisions" not in tables:
        op.create_table(
            "planned_meal_revisions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("cycle_id", sa.Integer(), sa.ForeignKey("meal_cycles.id", ondelete="CASCADE"), nullable=False),
            sa.Column("cycle_slot_id", sa.Integer(), nullable=False),
            sa.Column("planned_meal_id", sa.Integer(), nullable=False),
            sa.Column("action", sa.String(30), nullable=False),
            sa.Column("source_type", sa.String(30), nullable=False),
            sa.Column("snapshot_name", sa.String(160), nullable=False),
            sa.Column("snapshot_description", sa.Text(), nullable=True),
            sa.Column("planned_servings", sa.Numeric(10, 3), nullable=False),
            sa.Column("planned_leftover_servings", sa.Numeric(10, 3), nullable=False),
            sa.Column("component_serving_overrides", sa.Text(), nullable=False),
            sa.Column("scaled_components", sa.Text(), nullable=False),
            sa.Column("changed_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_planned_meal_revisions_cycle", "planned_meal_revisions", ["cycle_id", "id"])

    bind.execute(sa.text(
        "UPDATE shopping_list_items SET baseline_required_quantity = required_quantity "
        "WHERE baseline_required_quantity IS NULL"
    ))
    bind.execute(sa.text(
        "INSERT INTO shopping_item_purchases "
        "(shopping_list_item_id, actual_quantity, actual_unit_id, purchase_date, storage_location_id, expiration_date, purchase_notes, inventory_lot_id, completed_at) "
        "SELECT id, actual_quantity, actual_unit_id, purchase_date, storage_location_id, expiration_date, purchase_notes, inventory_lot_id, completed_at "
        "FROM shopping_list_items sli "
        "WHERE sli.status='COMPLETED' AND sli.actual_quantity IS NOT NULL AND sli.actual_unit_id IS NOT NULL "
        "AND sli.storage_location_id IS NOT NULL AND sli.inventory_lot_id IS NOT NULL AND sli.completed_at IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM shopping_item_purchases p WHERE p.inventory_lot_id=sli.inventory_lot_id)"
    ))


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "planned_meal_revisions" in tables:
        op.drop_index("ix_planned_meal_revisions_cycle", table_name="planned_meal_revisions")
        op.drop_table("planned_meal_revisions")
    if "shopping_item_purchases" in tables:
        op.drop_index("ix_shopping_item_purchases_item", table_name="shopping_item_purchases")
        op.drop_table("shopping_item_purchases")
    columns = _column_names(bind, "shopping_list_items")
    if "purchased_excess_quantity" in columns:
        op.drop_column("shopping_list_items", "purchased_excess_quantity")
    if "plan_delta_quantity" in columns:
        op.drop_column("shopping_list_items", "plan_delta_quantity")
    if "baseline_required_quantity" in columns:
        op.drop_column("shopping_list_items", "baseline_required_quantity")
