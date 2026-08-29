from __future__ import annotations

import argparse
import os
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import text


TEST_DB = Path(__file__).with_name("mealplanner-test.db").resolve()


def configure_database() -> None:
    os.environ["CYCLE_MEAL_PLANNER_DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
    os.environ["CYCLE_MEAL_PLANNER_ENV"] = "testdata"


def _clear_seeded_data(engine) -> None:
    """Clear mutable test data without deleting the SQLite file.

    Keeping the file in place makes --reset work on Windows even while the
    development server has the database open.
    """
    tables = [
        "shopping_list_items",
        "shopping_lists",
        "planned_meals",
        "cycle_slots",
        "meal_slot_definitions",
        "meal_cycles",
        "meal_tags",
        "meal_meal_types",
        "meal_recipes",
        "meals",
        "recipe_tags",
        "recipe_meal_types",
        "recipe_ingredients",
        "recipes",
        "inventory_transactions",
        "inventory_lots",
        "ingredient_aliases",
        "ingredients",
        "tags",
    ]
    with engine.begin() as connection:
        for table in tables:
            connection.execute(text(f"DELETE FROM {table}"))
        connection.execute(text("UPDATE households SET name='My Household', default_servings=4 WHERE id=1"))


def seed(reset: bool = False) -> Path:
    configure_database()

    from app.database.migrations import run_migrations
    from app.database.session import engine

    run_migrations()

    if reset:
        _clear_seeded_data(engine)
    elif TEST_DB.exists():
        with engine.connect() as connection:
            existing = connection.execute(text("SELECT COUNT(*) FROM ingredients")).scalar_one()
        if existing:
            return TEST_DB

    today = date.today()
    ingredients = [
        (1, "Chicken Breast", 2, 2, 3, True),
        (2, "Ground Beef", 2, 2, 3, True),
        (3, "Eggs", 3, 14, 2, True),
        (4, "Milk", 3, 8, 2, True),
        (5, "Cheddar Cheese", 3, 1, 2, True),
        (6, "Rice", 6, 8, 1, False),
        (7, "Pasta", 6, 2, 1, False),
        (8, "Tomato Sauce", 6, 8, 1, False),
        (9, "Bell Pepper", 1, 14, 2, True),
        (10, "Onion", 1, 14, 1, True),
        (11, "Potatoes", 1, 2, 1, True),
        (12, "Tortillas", 4, 14, 1, False),
        (13, "Black Beans", 6, 14, 1, False),
        (14, "Bread", 4, 14, 1, False),
        (15, "Butter", 3, 1, 2, True),
        (16, "Garlic", 1, 14, 1, True),
    ]
    recipes = [
        (1, "Chicken and Rice", "Chicken with seasoned rice", "DINNER", 25, [(1, 1, 2), (6, 2, 8), (10, 1, 14)]),
        (2, "Beef Tacos", "Simple ground beef tacos", "DINNER", 20, [(2, 1, 2), (12, 8, 14), (5, 4, 1)]),
        (3, "Spaghetti", "Pasta with tomato sauce", "DINNER", 25, [(7, 1, 2), (8, 2, 8), (16, 2, 14)]),
        (4, "Breakfast Scramble", "Eggs, cheese, peppers, and onion", "BREAKFAST", 15, [(3, 8, 14), (5, 4, 1), (9, 1, 14)]),
        (5, "Grilled Cheese", "Classic grilled cheese sandwiches", "LUNCH", 10, [(14, 8, 14), (5, 8, 1), (15, 2, 6)]),
        (6, "Loaded Baked Potatoes", "Baked potatoes with cheese and butter", "DINNER", 55, [(11, 4, 14), (5, 4, 1), (15, 2, 6)]),
        (7, "Bean Quesadillas", "Black bean and cheese quesadillas", "LUNCH", 15, [(12, 8, 14), (13, 2, 14), (5, 6, 1)]),
        (8, "Chicken Quesadillas", "Chicken and cheese quesadillas", "DINNER", 20, [(1, 1, 2), (12, 8, 14), (5, 6, 1)]),
        (9, "Egg Toast", "Eggs and buttered toast", "BREAKFAST", 10, [(3, 4, 14), (14, 4, 14), (15, 1, 6)]),
        (10, "Beef and Potatoes", "Ground beef skillet with potatoes", "DINNER", 35, [(2, 1, 2), (11, 2, 2), (10, 1, 14)]),
        (11, "Pasta Bake", "Cheesy baked pasta", "DINNER", 45, [(7, 1, 2), (8, 2, 8), (5, 8, 1)]),
        (12, "Breakfast Quesadilla", "Egg and cheese breakfast quesadilla", "BREAKFAST", 15, [(3, 6, 14), (12, 4, 14), (5, 4, 1)]),
    ]
    meals = [
        (1, "Chicken Dinner", "Chicken and rice dinner", "DINNER", 1),
        (2, "Taco Night", "Beef taco night", "DINNER", 2),
        (3, "Spaghetti Night", "Spaghetti dinner", "DINNER", 3),
        (4, "Breakfast Scramble Meal", "Scramble breakfast", "BREAKFAST", 4),
        (5, "Grilled Cheese Lunch", "Quick lunch", "LUNCH", 5),
        (6, "Loaded Potato Dinner", "Loaded potatoes", "DINNER", 6),
        (7, "Quesadilla Lunch", "Bean quesadilla lunch", "LUNCH", 7),
        (8, "Chicken Quesadilla Dinner", "Chicken quesadillas", "DINNER", 8),
        (9, "Egg Toast Breakfast", "Egg toast breakfast", "BREAKFAST", 9),
        (10, "Beef Skillet Dinner", "Beef and potatoes", "DINNER", 10),
        (11, "Pasta Bake Night", "Pasta bake dinner", "DINNER", 11),
        (12, "Breakfast Quesadilla Meal", "Breakfast quesadilla", "BREAKFAST", 12),
    ]

    with engine.begin() as connection:
        connection.execute(text("UPDATE households SET name='Test Household' WHERE id=1"))
        connection.execute(text("INSERT INTO tags (id, household_id, name, normalized_name, category, active) VALUES (1,1,'Quick','quick','STYLE',1),(2,1,'Family Favorite','family favorite','STYLE',1),(3,1,'Freezer Friendly','freezer friendly','STYLE',1),(4,1,'Weeknight','weeknight','STYLE',1)"))

        for ingredient_id, name, category_id, unit_id, location_id, perishable in ingredients:
            connection.execute(
                text("""
                    INSERT INTO ingredients
                    (id, household_id, name, normalized_name, shopping_category_id, preferred_unit_id, default_location_id, perishable, active, notes)
                    VALUES (:id, 1, :name, :normalized, :category, :unit, :location, :perishable, 1, 'Seeded test ingredient')
                """),
                {"id": ingredient_id, "name": name, "normalized": name.casefold(), "category": category_id, "unit": unit_id, "location": location_id, "perishable": perishable},
            )

        recipe_ingredient_id = 1
        for recipe_id, name, description, meal_type, cook_minutes, recipe_ingredients in recipes:
            connection.execute(
                text("""
                    INSERT INTO recipes
                    (id, household_id, name, normalized_name, description, base_servings, serving_unit, prep_time_minutes, cook_time_minutes, favorite, active)
                    VALUES (:id, 1, :name, :normalized, :description, 4, 'servings', 10, :cook, :favorite, 1)
                """),
                {"id": recipe_id, "name": name, "normalized": name.casefold(), "description": description, "cook": cook_minutes, "favorite": recipe_id in (1, 2, 4)},
            )
            connection.execute(text("INSERT INTO recipe_meal_types (recipe_id, meal_type) VALUES (:id, :meal_type)"), {"id": recipe_id, "meal_type": meal_type})
            connection.execute(text("INSERT INTO recipe_tags (recipe_id, tag_id) VALUES (:id, :tag_id)"), {"id": recipe_id, "tag_id": 1 if recipe_id in (2, 4, 5, 7, 9, 12) else 4})
            for sort_order, (ingredient_id, quantity, unit_id) in enumerate(recipe_ingredients):
                connection.execute(
                    text("""
                        INSERT INTO recipe_ingredients
                        (id, recipe_id, ingredient_id, quantity, unit_id, optional, scaling_mode, required_state, sort_order)
                        VALUES (:id, :recipe, :ingredient, :quantity, :unit, 0, 'LINEAR', 'ANY', :sort_order)
                    """),
                    {"id": recipe_ingredient_id, "recipe": recipe_id, "ingredient": ingredient_id, "quantity": quantity, "unit": unit_id, "sort_order": sort_order},
                )
                recipe_ingredient_id += 1

        for meal_id, name, description, meal_type, recipe_id in meals:
            connection.execute(
                text("""
                    INSERT INTO meals (id, household_id, name, normalized_name, description, favorite, active)
                    VALUES (:id, 1, :name, :normalized, :description, :favorite, 1)
                """),
                {"id": meal_id, "name": name, "normalized": name.casefold(), "description": description, "favorite": meal_id in (1, 2, 4)},
            )
            connection.execute(text("INSERT INTO meal_meal_types (meal_id, meal_type) VALUES (:id, :meal_type)"), {"id": meal_id, "meal_type": meal_type})
            connection.execute(text("INSERT INTO meal_recipes (id, meal_id, recipe_id, serving_multiplier, sort_order) VALUES (:id, :meal, :recipe, 1, 0)"), {"id": meal_id, "meal": meal_id, "recipe": recipe_id})

        inventory = [
            (1, 1, 3, 3, 2, 10), (2, 2, 3, 2, 2, 30), (3, 3, 2, 18, 14, 21), (4, 4, 2, 1, 8, 7),
            (5, 5, 2, 12, 1, 20), (6, 6, 1, 6, 8, None), (7, 7, 1, 4, 2, None), (8, 8, 1, 5, 8, None),
            (9, 9, 2, 4, 14, 8), (10, 10, 1, 6, 14, 25), (11, 11, 1, 10, 2, 40), (12, 12, 1, 24, 14, 14),
            (13, 13, 1, 8, 14, None), (14, 14, 1, 2, 14, 9), (15, 15, 2, 1, 2, 25), (16, 16, 1, 10, 14, 30),
        ]
        for lot_id, ingredient_id, location_id, quantity, unit_id, expires_in in inventory:
            expiration = today + timedelta(days=expires_in) if expires_in is not None else None
            connection.execute(
                text("""
                    INSERT INTO inventory_lots
                    (id, household_id, ingredient_id, location_id, quantity, unit_id, purchase_date, expiration_date, notes)
                    VALUES (:id, 1, :ingredient, :location, :quantity, :unit, :purchase, :expiration, 'Seeded test inventory')
                """),
                {"id": lot_id, "ingredient": ingredient_id, "location": location_id, "quantity": quantity, "unit": unit_id, "purchase": today, "expiration": expiration},
            )
            connection.execute(
                text("""
                    INSERT INTO inventory_transactions
                    (household_id, lot_id, transaction_type, quantity_delta, unit_id, to_location_id, note)
                    VALUES (1, :lot, 'PURCHASE', :quantity, :unit, :location, 'Seeded test data')
                """),
                {"lot": lot_id, "quantity": quantity, "unit": unit_id, "location": location_id},
            )

        connection.execute(text("INSERT INTO meal_cycles (id, household_id, name, normalized_name, duration_days, status, notes) VALUES (1,1,'Sample Week','sample week',7,'DRAFT','Seeded cycle for placement testing')"))
        slot_definitions = [(1, "Breakfast", 0), (2, "Lunch", 1), (3, "Dinner", 2)]
        for definition_id, label, sort_order in slot_definitions:
            connection.execute(text("INSERT INTO meal_slot_definitions (id, cycle_id, label, sort_order) VALUES (:id,1,:label,:sort_order)"), {"id": definition_id, "label": label, "sort_order": sort_order})
        slot_id = 1
        for day_number in range(1, 8):
            for definition_id, _label, sort_order in slot_definitions:
                connection.execute(text("INSERT INTO cycle_slots (id, cycle_id, slot_definition_id, day_number, sort_order) VALUES (:id,1,:definition,:day,:sort_order)"), {"id": slot_id, "definition": definition_id, "day": day_number, "sort_order": sort_order})
                slot_id += 1

    print(f"Reset test database: {TEST_DB}" if reset else f"Created test database: {TEST_DB}")
    print("Seeded: 16 ingredients, 12 recipes, 12 meals, 16 inventory lots, 1 seven-day cycle")
    return TEST_DB


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or reset the Cycle Meal Planner test database.")
    parser.add_argument("--reset", action="store_true", help="Clear and rebuild seeded test data in place.")
    args = parser.parse_args()
    seed(reset=args.reset)


if __name__ == "__main__":
    main()
