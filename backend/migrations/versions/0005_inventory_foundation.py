"""inventory foundation

Revision ID: 0005_inventory_foundation
Revises: 0004_recipe_backend
Create Date: 2026-08-29
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0005_inventory_foundation"
down_revision: str | None = "0004_recipe_backend"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inventory_lots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("household_id", sa.Integer(), sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ingredient_id", sa.Integer(), sa.ForeignKey("ingredients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("inventory_locations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 6), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("measurement_units.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("purchase_date", sa.Date()),
        sa.Column("opened_date", sa.Date()),
        sa.Column("expiration_date", sa.Date()),
        sa.Column("frozen_date", sa.Date()),
        sa.Column("thawed_date", sa.Date()),
        sa.Column("notes", sa.Text()),
        sa.CheckConstraint("quantity >= 0", name="ck_inventory_lots_quantity_nonnegative"),
    )
    op.create_index("ix_inventory_lots_ingredient", "inventory_lots", ["ingredient_id"])
    op.create_index("ix_inventory_lots_location", "inventory_lots", ["location_id"])
    op.create_index("ix_inventory_lots_expiration", "inventory_lots", ["expiration_date"])

    op.create_table(
        "inventory_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("household_id", sa.Integer(), sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lot_id", sa.Integer(), sa.ForeignKey("inventory_lots.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("transaction_type", sa.String(30), nullable=False),
        sa.Column("quantity_delta", sa.Numeric(14, 6), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("measurement_units.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("from_location_id", sa.Integer(), sa.ForeignKey("inventory_locations.id", ondelete="RESTRICT")),
        sa.Column("to_location_id", sa.Integer(), sa.ForeignKey("inventory_locations.id", ondelete="RESTRICT")),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.CheckConstraint(
            "transaction_type IN ('PURCHASE','CONSUME','TRANSFER','MANUAL_ADD','MANUAL_REMOVE','CORRECTION')",
            name="ck_inventory_transactions_type",
        ),
    )
    op.create_index("ix_inventory_transactions_lot", "inventory_transactions", ["lot_id"])


def downgrade() -> None:
    op.drop_index("ix_inventory_transactions_lot", table_name="inventory_transactions")
    op.drop_table("inventory_transactions")
    op.drop_index("ix_inventory_lots_expiration", table_name="inventory_lots")
    op.drop_index("ix_inventory_lots_location", table_name="inventory_lots")
    op.drop_index("ix_inventory_lots_ingredient", table_name="inventory_lots")
    op.drop_table("inventory_lots")
