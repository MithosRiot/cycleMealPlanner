"""core reference data

Revision ID: 0002_core_reference_data
Revises: 0001_initial_foundation
Create Date: 2026-08-29
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_core_reference_data"
down_revision = "0001_initial_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "households",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("default_servings", sa.Numeric(10, 3), nullable=False),
        sa.CheckConstraint("default_servings > 0", name="ck_households_default_servings_positive"),
    )
    op.create_table(
        "measurement_units",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=20), nullable=False, unique=True),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("unit_family", sa.String(length=20), nullable=False),
        sa.Column("base_multiplier", sa.Numeric(18, 8), nullable=False),
        sa.Column("allows_fraction", sa.Boolean(), nullable=False),
        sa.CheckConstraint("base_multiplier > 0", name="ck_units_multiplier_positive"),
    )
    op.create_table(
        "shopping_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("household_id", sa.Integer(), sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("household_id", "name", name="uq_shopping_categories_household_name"),
        sa.CheckConstraint("sort_order >= 0", name="ck_shopping_categories_sort_order"),
    )
    op.create_table(
        "inventory_locations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("household_id", sa.Integer(), sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_location_id", sa.Integer(), sa.ForeignKey("inventory_locations.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("location_type", sa.String(length=30), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("household_id", "parent_location_id", "name", name="uq_inventory_locations_sibling_name"),
        sa.CheckConstraint("sort_order >= 0", name="ck_inventory_locations_sort_order"),
    )

    household = sa.table(
        "households",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("default_servings", sa.Numeric),
    )
    units = sa.table(
        "measurement_units",
        sa.column("id", sa.Integer),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("unit_family", sa.String),
        sa.column("base_multiplier", sa.Numeric),
        sa.column("allows_fraction", sa.Boolean),
    )
    categories = sa.table(
        "shopping_categories",
        sa.column("id", sa.Integer),
        sa.column("household_id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("sort_order", sa.Integer),
        sa.column("active", sa.Boolean),
    )
    locations = sa.table(
        "inventory_locations",
        sa.column("id", sa.Integer),
        sa.column("household_id", sa.Integer),
        sa.column("parent_location_id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("location_type", sa.String),
        sa.column("sort_order", sa.Integer),
        sa.column("active", sa.Boolean),
    )

    op.bulk_insert(household, [{"id": 1, "name": "My Household", "default_servings": 4}])
    op.bulk_insert(
        units,
        [
            {"id": 1, "code": "oz", "name": "ounce", "unit_family": "WEIGHT", "base_multiplier": 1, "allows_fraction": True},
            {"id": 2, "code": "lb", "name": "pound", "unit_family": "WEIGHT", "base_multiplier": 16, "allows_fraction": True},
            {"id": 3, "code": "g", "name": "gram", "unit_family": "WEIGHT", "base_multiplier": "0.03527396", "allows_fraction": True},
            {"id": 4, "code": "kg", "name": "kilogram", "unit_family": "WEIGHT", "base_multiplier": "35.27396195", "allows_fraction": True},
            {"id": 5, "code": "tsp", "name": "teaspoon", "unit_family": "VOLUME", "base_multiplier": 1, "allows_fraction": True},
            {"id": 6, "code": "tbsp", "name": "tablespoon", "unit_family": "VOLUME", "base_multiplier": 3, "allows_fraction": True},
            {"id": 7, "code": "fl_oz", "name": "fluid ounce", "unit_family": "VOLUME", "base_multiplier": 6, "allows_fraction": True},
            {"id": 8, "code": "cup", "name": "cup", "unit_family": "VOLUME", "base_multiplier": 48, "allows_fraction": True},
            {"id": 9, "code": "pint", "name": "pint", "unit_family": "VOLUME", "base_multiplier": 96, "allows_fraction": True},
            {"id": 10, "code": "quart", "name": "quart", "unit_family": "VOLUME", "base_multiplier": 192, "allows_fraction": True},
            {"id": 11, "code": "gallon", "name": "gallon", "unit_family": "VOLUME", "base_multiplier": 768, "allows_fraction": True},
            {"id": 12, "code": "ml", "name": "milliliter", "unit_family": "VOLUME", "base_multiplier": "0.20288414", "allows_fraction": True},
            {"id": 13, "code": "L", "name": "liter", "unit_family": "VOLUME", "base_multiplier": "202.88413535", "allows_fraction": True},
            {"id": 14, "code": "each", "name": "each", "unit_family": "COUNT", "base_multiplier": 1, "allows_fraction": False},
            {"id": 15, "code": "dozen", "name": "dozen", "unit_family": "COUNT", "base_multiplier": 12, "allows_fraction": True},
        ],
    )
    op.bulk_insert(
        categories,
        [
            {"id": 1, "household_id": 1, "name": "Produce", "sort_order": 10, "active": True},
            {"id": 2, "household_id": 1, "name": "Meat", "sort_order": 20, "active": True},
            {"id": 3, "household_id": 1, "name": "Dairy", "sort_order": 30, "active": True},
            {"id": 4, "household_id": 1, "name": "Bakery", "sort_order": 40, "active": True},
            {"id": 5, "household_id": 1, "name": "Frozen", "sort_order": 50, "active": True},
            {"id": 6, "household_id": 1, "name": "Pantry", "sort_order": 60, "active": True},
            {"id": 7, "household_id": 1, "name": "Spices", "sort_order": 70, "active": True},
            {"id": 8, "household_id": 1, "name": "Condiments", "sort_order": 80, "active": True},
            {"id": 9, "household_id": 1, "name": "Household", "sort_order": 90, "active": True},
            {"id": 10, "household_id": 1, "name": "Other", "sort_order": 100, "active": True},
        ],
    )
    op.bulk_insert(
        locations,
        [
            {"id": 1, "household_id": 1, "parent_location_id": None, "name": "Pantry", "location_type": "PANTRY", "sort_order": 10, "active": True},
            {"id": 2, "household_id": 1, "parent_location_id": None, "name": "Refrigerator", "location_type": "REFRIGERATOR", "sort_order": 20, "active": True},
            {"id": 3, "household_id": 1, "parent_location_id": None, "name": "Freezer", "location_type": "FREEZER", "sort_order": 30, "active": True},
            {"id": 4, "household_id": 1, "parent_location_id": None, "name": "Spice Drawer", "location_type": "SPICE", "sort_order": 40, "active": True},
        ],
    )


def downgrade() -> None:
    op.drop_table("inventory_locations")
    op.drop_table("shopping_categories")
    op.drop_table("measurement_units")
    op.drop_table("households")
