from alembic import op
import sqlalchemy as sa

revision = "0006_saved_meals"
down_revision = "0005_inventory_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("normalized_name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("favorite", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("household_id", "normalized_name", name="uq_meals_household_normalized_name"),
    )
    op.create_table(
        "meal_recipes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("meal_id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("serving_multiplier", sa.Numeric(10, 3), nullable=False),
        sa.Column("default_servings", sa.Numeric(10, 3), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint("serving_multiplier > 0", name="ck_meal_recipes_serving_multiplier_positive"),
        sa.CheckConstraint("default_servings IS NULL OR default_servings > 0", name="ck_meal_recipes_default_servings_positive"),
        sa.CheckConstraint("sort_order >= 0", name="ck_meal_recipes_sort_order_nonnegative"),
        sa.ForeignKeyConstraint(["meal_id"], ["meals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="RESTRICT"),
    )
    op.create_table(
        "meal_meal_types",
        sa.Column("meal_id", sa.Integer(), nullable=False),
        sa.Column("meal_type", sa.String(length=30), nullable=False),
        sa.ForeignKeyConstraint(["meal_id"], ["meals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("meal_id", "meal_type"),
    )
    op.create_table(
        "meal_tags",
        sa.Column("meal_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["meal_id"], ["meals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("meal_id", "tag_id"),
    )


def downgrade() -> None:
    op.drop_table("meal_tags")
    op.drop_table("meal_meal_types")
    op.drop_table("meal_recipes")
    op.drop_table("meals")
