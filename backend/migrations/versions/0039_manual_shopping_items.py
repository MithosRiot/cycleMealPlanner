"""add manual shopping items

Revision ID: 0039_manual_shopping_items
Revises: 0038_inventory_waste_spoilage
Create Date: 2026-09-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0039_manual_shopping_items"
down_revision: Union[str, None] = "0038_inventory_waste_spoilage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE_NAME = "manual_shopping_items"
INDEX_NAME = "ix_manual_shopping_items_shopping_list_id"


def _create_table() -> None:
    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("shopping_list_id", sa.Integer(), sa.ForeignKey("shopping_lists.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("quantity", sa.Numeric(16, 6), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("measurement_units.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("shopping_category_id", sa.Integer(), sa.ForeignKey("shopping_categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("ingredient_id", sa.Integer(), sa.ForeignKey("ingredients.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("inventory_lot_id", sa.Integer(), sa.ForeignKey("inventory_lots.id", ondelete="RESTRICT"), nullable=True, unique=True),
        sa.Column("purchase_date", sa.Date(), nullable=True),
        sa.Column("storage_location_id", sa.Integer(), sa.ForeignKey("inventory_locations.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("expiration_date", sa.Date(), nullable=True),
        sa.CheckConstraint("quantity > 0", name="ck_manual_shopping_items_quantity_positive"),
        sa.CheckConstraint("status IN ('PENDING','COMPLETED','SKIPPED')", name="ck_manual_shopping_items_status"),
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE_NAME not in inspector.get_table_names():
        _create_table()
        inspector = sa.inspect(bind)

    indexes = {row["name"] for row in inspector.get_indexes(TABLE_NAME) if row.get("name")}
    if INDEX_NAME not in indexes:
        op.create_index(INDEX_NAME, TABLE_NAME, ["shopping_list_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE_NAME not in inspector.get_table_names():
        return
    indexes = {row["name"] for row in inspector.get_indexes(TABLE_NAME) if row.get("name")}
    if INDEX_NAME in indexes:
        op.drop_index(INDEX_NAME, table_name=TABLE_NAME)
    op.drop_table(TABLE_NAME)
