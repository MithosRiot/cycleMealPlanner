"""shopping completion

Revision ID: 0011_shopping_completion
Revises: 0010_shopping_lists
Create Date: 2026-08-29
"""

from alembic import op
import sqlalchemy as sa

revision = "0011_shopping_completion"
down_revision = "0010_shopping_lists"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("shopping_list_items") as batch_op:
        batch_op.add_column(sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"))
        batch_op.add_column(sa.Column("actual_quantity", sa.Numeric(16, 6)))
        batch_op.add_column(sa.Column("actual_unit_id", sa.Integer(), sa.ForeignKey("measurement_units.id", ondelete="RESTRICT")))
        batch_op.add_column(sa.Column("purchase_date", sa.Date()))
        batch_op.add_column(sa.Column("storage_location_id", sa.Integer(), sa.ForeignKey("inventory_locations.id", ondelete="RESTRICT")))
        batch_op.add_column(sa.Column("expiration_date", sa.Date()))
        batch_op.add_column(sa.Column("purchase_notes", sa.Text()))
        batch_op.add_column(sa.Column("inventory_lot_id", sa.Integer(), sa.ForeignKey("inventory_lots.id", ondelete="RESTRICT")))
        batch_op.add_column(sa.Column("completed_at", sa.DateTime()))
        batch_op.create_unique_constraint("uq_shopping_item_inventory_lot", ["inventory_lot_id"])


def downgrade() -> None:
    with op.batch_alter_table("shopping_list_items") as batch_op:
        batch_op.drop_constraint("uq_shopping_item_inventory_lot", type_="unique")
        batch_op.drop_column("completed_at")
        batch_op.drop_column("inventory_lot_id")
        batch_op.drop_column("purchase_notes")
        batch_op.drop_column("expiration_date")
        batch_op.drop_column("storage_location_id")
        batch_op.drop_column("purchase_date")
        batch_op.drop_column("actual_unit_id")
        batch_op.drop_column("actual_quantity")
        batch_op.drop_column("status")
