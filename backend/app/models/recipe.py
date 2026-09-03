from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, Integer, Numeric, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.ingredient import Tag


recipe_tags = Table(
    "recipe_tags",
    Base.metadata,
    Column("recipe_id", ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="RESTRICT"), primary_key=True),
)


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    base_servings: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    serving_unit: Mapped[str] = mapped_column(String(40), nullable=False, default="servings")
    yield_quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    yield_unit_id: Mapped[int | None] = mapped_column(ForeignKey("measurement_units.id", ondelete="SET NULL"))
    prep_time_minutes: Mapped[int | None] = mapped_column(Integer)
    cook_time_minutes: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    prep_groups: Mapped[list[RecipePrepGroup]] = relationship(back_populates="recipe", cascade="all, delete-orphan", order_by="RecipePrepGroup.sort_order")
    advance_prep: Mapped[list[RecipeAdvancePrep]] = relationship(back_populates="recipe", cascade="all, delete-orphan", order_by="RecipeAdvancePrep.sort_order")
    equipment: Mapped[list[RecipeEquipment]] = relationship(back_populates="recipe", cascade="all, delete-orphan", order_by="RecipeEquipment.sort_order")
    ingredients: Mapped[list[RecipeIngredient]] = relationship(back_populates="recipe", cascade="all, delete-orphan", order_by="RecipeIngredient.sort_order")
    variants: Mapped[list[RecipeVariant]] = relationship(back_populates="recipe", cascade="all, delete-orphan", order_by="RecipeVariant.sort_order")
    meal_types: Mapped[list[RecipeMealType]] = relationship(back_populates="recipe", cascade="all, delete-orphan", order_by="RecipeMealType.meal_type")
    tags: Mapped[list[Tag]] = relationship(secondary=recipe_tags)

    __table_args__ = (
        UniqueConstraint("household_id", "normalized_name", name="uq_recipes_household_normalized_name"),
        CheckConstraint("base_servings > 0", name="ck_recipes_base_servings_positive"),
        CheckConstraint("yield_quantity IS NULL OR yield_quantity > 0", name="ck_recipes_yield_quantity_positive"),
        CheckConstraint("prep_time_minutes IS NULL OR prep_time_minutes >= 0", name="ck_recipes_prep_time_nonnegative"),
        CheckConstraint("cook_time_minutes IS NULL OR cook_time_minutes >= 0", name="ck_recipes_cook_time_nonnegative"),
    )


class RecipePrepGroup(Base):
    __tablename__ = "recipe_prep_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    recipe: Mapped[Recipe] = relationship(back_populates="prep_groups")

    __table_args__ = (CheckConstraint("sort_order >= 0", name="ck_recipe_prep_groups_sort_order_nonnegative"),)


class RecipeAdvancePrep(Base):
    __tablename__ = "recipe_advance_prep"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    prep_group_id: Mapped[int | None] = mapped_column(ForeignKey("recipe_prep_groups.id", ondelete="SET NULL"))
    task_type: Mapped[str] = mapped_column(String(20), nullable=False, default="PREP")
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    lead_time_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    instructions: Mapped[str | None] = mapped_column(Text)
    reminder_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reminder_offset_minutes: Mapped[int | None] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    recipe: Mapped[Recipe] = relationship(back_populates="advance_prep")

    __table_args__ = (
        CheckConstraint("task_type IN ('PREP','THAW','MARINATE','SOAK','PROOF')", name="ck_recipe_advance_prep_task_type"),
        CheckConstraint("lead_time_minutes >= 0", name="ck_recipe_advance_prep_lead_nonnegative"),
        CheckConstraint("duration_minutes IS NULL OR duration_minutes >= 0", name="ck_recipe_advance_prep_duration_nonnegative"),
        CheckConstraint("reminder_offset_minutes IS NULL OR reminder_offset_minutes >= 0", name="ck_recipe_advance_prep_reminder_offset_nonnegative"),
        CheckConstraint("reminder_enabled = 0 OR reminder_offset_minutes IS NOT NULL", name="ck_recipe_advance_prep_reminder_enabled_has_offset"),
        CheckConstraint("sort_order >= 0", name="ck_recipe_advance_prep_sort_order_nonnegative"),
    )


class RecipeEquipment(Base):
    __tablename__ = "recipe_equipment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    notes: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    recipe: Mapped[Recipe] = relationship(back_populates="equipment")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_recipe_equipment_quantity_positive"),
        CheckConstraint("sort_order >= 0", name="ck_recipe_equipment_sort_order_nonnegative"),
        UniqueConstraint("recipe_id", "equipment_id", name="uq_recipe_equipment_recipe_equipment"),
    )


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id", ondelete="RESTRICT"), nullable=False)
    prep_group_id: Mapped[int | None] = mapped_column(ForeignKey("recipe_prep_groups.id", ondelete="SET NULL"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    unit_id: Mapped[int] = mapped_column(ForeignKey("measurement_units.id", ondelete="RESTRICT"), nullable=False)
    display_text: Mapped[str | None] = mapped_column(String(160))
    preparation: Mapped[str | None] = mapped_column(String(160))
    prep_method: Mapped[str | None] = mapped_column(String(80))
    prep_size: Mapped[str | None] = mapped_column(String(80))
    prep_state: Mapped[str | None] = mapped_column(String(80))
    optional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    scaling_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="LINEAR")
    required_state: Mapped[str] = mapped_column(String(30), nullable=False, default="ANY")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text)

    recipe: Mapped[Recipe] = relationship(back_populates="ingredients")
    substitutions: Mapped[list[RecipeIngredientSubstitution]] = relationship(back_populates="recipe_ingredient", cascade="all, delete-orphan", order_by="RecipeIngredientSubstitution.sort_order")

    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_recipe_ingredients_quantity_nonnegative"),
        CheckConstraint("sort_order >= 0", name="ck_recipe_ingredients_sort_order_nonnegative"),
        CheckConstraint("scaling_mode IN ('LINEAR','FIXED','ROUND_UP','MANUAL')", name="ck_recipe_ingredients_scaling_mode"),
    )


class RecipeIngredientSubstitution(Base):
    __tablename__ = "recipe_ingredient_substitutions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_ingredient_id: Mapped[int] = mapped_column(ForeignKey("recipe_ingredients.id", ondelete="CASCADE"), nullable=False)
    substitute_ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id", ondelete="RESTRICT"), nullable=False)
    ratio: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False, default=Decimal("1"))
    preferred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    recipe_ingredient: Mapped[RecipeIngredient] = relationship(back_populates="substitutions")

    __table_args__ = (
        CheckConstraint("ratio > 0", name="ck_recipe_ingredient_substitutions_ratio_positive"),
        CheckConstraint("sort_order >= 0", name="ck_recipe_ingredient_substitutions_sort_order_nonnegative"),
        UniqueConstraint("recipe_ingredient_id", "substitute_ingredient_id", name="uq_recipe_ingredient_substitutions_alternate"),
    )


class RecipeVariant(Base):
    __tablename__ = "recipe_variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(160), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    recipe: Mapped[Recipe] = relationship(back_populates="variants")
    overrides: Mapped[list[RecipeVariantIngredientOverride]] = relationship(back_populates="variant", cascade="all, delete-orphan", order_by="RecipeVariantIngredientOverride.id")

    __table_args__ = (
        UniqueConstraint("recipe_id", "normalized_name", name="uq_recipe_variants_recipe_normalized_name"),
        CheckConstraint("sort_order >= 0", name="ck_recipe_variants_sort_order_nonnegative"),
    )


class RecipeVariantIngredientOverride(Base):
    __tablename__ = "recipe_variant_ingredient_overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey("recipe_variants.id", ondelete="CASCADE"), nullable=False)
    recipe_ingredient_id: Mapped[int] = mapped_column(ForeignKey("recipe_ingredients.id", ondelete="CASCADE"), nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 6))
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("measurement_units.id", ondelete="RESTRICT"))
    substitution_id: Mapped[int | None] = mapped_column(ForeignKey("recipe_ingredient_substitutions.id", ondelete="SET NULL"))
    preparation: Mapped[str | None] = mapped_column(String(160))
    prep_method: Mapped[str | None] = mapped_column(String(80))
    prep_size: Mapped[str | None] = mapped_column(String(80))
    prep_state: Mapped[str | None] = mapped_column(String(80))
    notes: Mapped[str | None] = mapped_column(Text)

    variant: Mapped[RecipeVariant] = relationship(back_populates="overrides")

    __table_args__ = (
        UniqueConstraint("variant_id", "recipe_ingredient_id", name="uq_recipe_variant_override_ingredient"),
        CheckConstraint("quantity IS NULL OR quantity >= 0", name="ck_recipe_variant_override_quantity_nonnegative"),
    )


class RecipeMealType(Base):
    __tablename__ = "recipe_meal_types"

    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True)
    meal_type: Mapped[str] = mapped_column(String(30), primary_key=True)

    recipe: Mapped[Recipe] = relationship(back_populates="meal_types")
