"""add Shopping partial purchase and substitution provenance

Revision ID: 0037_shopping_partial_substitutions
Revises: 0036_active_cycle_shopping_deltas
Create Date: 2026-09-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0037_shopping_partial_substitutions"
down_revision: Union[str, None] = "0036_active_cycle_shopping_deltas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(bind, table_name: str) -> set[str]:
    return {row["name"] for row in sa.inspect(bind).get_columns(table_name)}


def _index_names(bind, table_name: str) -> set[str]:
    return {row["name"] for row in sa.inspect(bind).get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    columns = _column_names(bind, "shopping_item_purchases")

    if "purchased_ingredient_id" not in columns:
        op.add_column("shopping_item_purchases", sa.Column("purchased_ingredient_id", sa.Integer(), nullable=True))
    if "satisfied_quantity" not in columns:
        op.add_column("shopping_item_purchases", sa.Column("satisfied_quantity", sa.Numeric(16, 6), nullable=True))
    if "satisfied_unit_id" not in columns:
        op.add_column("shopping_item_purchases", sa.Column("satisfied_unit_id", sa.Integer(), nullable=True))
    if "purchase_kind" not in columns:
        op.add_column(
            "shopping_item_purchases",
            sa.Column("purchase_kind", sa.String(20), nullable=False, server_default="STANDARD"),
        )
    if "idempotency_key" not in columns:
        op.add_column("shopping_item_purchases", sa.Column("idempotency_key", sa.String(64), nullable=True))

    indexes = _index_names(bind, "shopping_item_purchases")
    if "ux_shopping_item_purchases_idempotency" not in indexes:
        op.create_index(
            "ux_shopping_item_purchases_idempotency",
            "shopping_item_purchases",
            ["idempotency_key"],
            unique=True,
        )

    bind.execute(sa.text("""
        UPDATE shopping_item_purchases
        SET purchased_ingredient_id = (
            SELECT sli.ingredient_id
            FROM shopping_list_items sli
            WHERE sli.id = shopping_item_purchases.shopping_list_item_id
        )
        WHERE purchased_ingredient_id IS NULL
    """))
    bind.execute(sa.text("""
        UPDATE shopping_item_purchases
        SET satisfied_quantity = actual_quantity,
            satisfied_unit_id = actual_unit_id,
            purchase_kind = 'STANDARD'
        WHERE satisfied_quantity IS NULL OR satisfied_unit_id IS NULL
    """))


def downgrade() -> None:
    bind = op.get_bind()
    indexes = _index_names(bind, "shopping_item_purchases")
    if "ux_shopping_item_purchases_idempotency" in indexes:
        op.drop_index("ux_shopping_item_purchases_idempotency", table_name="shopping_item_purchases")

    columns = _column_names(bind, "shopping_item_purchases")
    if "idempotency_key" in columns:
        op.drop_column("shopping_item_purchases", "idempotency_key")
    if "purchase_kind" in columns:
        op.drop_column("shopping_item_purchases", "purchase_kind")
    if "satisfied_unit_id" in columns:
        op.drop_column("shopping_item_purchases", "satisfied_unit_id")
    if "satisfied_quantity" in columns:
        op.drop_column("shopping_item_purchases", "satisfied_quantity")
    if "purchased_ingredient_id" in columns:
        op.drop_column("shopping_item_purchases", "purchased_ingredient_id")
