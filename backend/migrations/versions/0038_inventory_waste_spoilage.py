"""add waste and spoilage inventory transactions

Revision ID: 0038_inventory_waste_spoilage
Revises: 0037_shopping_partial_substitutions
Create Date: 2026-09-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0038_inventory_waste_spoilage"
down_revision: Union[str, None] = "0037_shopping_partial_substitutions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _check_map(bind, table_name: str) -> dict[str, dict]:
    return {
        row["name"]: row
        for row in sa.inspect(bind).get_check_constraints(table_name)
        if row.get("name")
    }


def _column_names(bind, table_name: str) -> set[str]:
    return {row["name"] for row in sa.inspect(bind).get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    if "reason" not in _column_names(bind, "inventory_transactions"):
        op.add_column("inventory_transactions", sa.Column("reason", sa.String(length=160), nullable=True))

    checks = _check_map(bind, "inventory_transactions")
    current = checks.get("ck_inventory_transactions_type")
    sql = str(current.get("sqltext", "")) if current else ""
    if "WASTE" not in sql or "SPOILAGE" not in sql:
        with op.batch_alter_table("inventory_transactions") as batch:
            if current is not None:
                batch.drop_constraint("ck_inventory_transactions_type", type_="check")
            batch.create_check_constraint(
                "ck_inventory_transactions_type",
                "transaction_type IN ('PURCHASE','CONSUME','TRANSFER','MANUAL_ADD','MANUAL_REMOVE','CORRECTION','PRODUCTION','WASTE','SPOILAGE')",
            )


def downgrade() -> None:
    bind = op.get_bind()
    count = bind.execute(sa.text(
        "SELECT COUNT(*) FROM inventory_transactions WHERE transaction_type IN ('WASTE','SPOILAGE')"
    )).scalar_one()
    if count:
        raise RuntimeError("Cannot downgrade 0038 while WASTE/SPOILAGE transactions exist")

    checks = _check_map(bind, "inventory_transactions")
    current = checks.get("ck_inventory_transactions_type")
    with op.batch_alter_table("inventory_transactions") as batch:
        if current is not None:
            batch.drop_constraint("ck_inventory_transactions_type", type_="check")
        batch.create_check_constraint(
            "ck_inventory_transactions_type",
            "transaction_type IN ('PURCHASE','CONSUME','TRANSFER','MANUAL_ADD','MANUAL_REMOVE','CORRECTION','PRODUCTION')",
        )
        if "reason" in _column_names(bind, "inventory_transactions"):
            batch.drop_column("reason")
