from __future__ import annotations

import argparse
import json
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
    development server has the database open. Tables are deleted in dependency
    order so every newly-added seeded feature can be reset safely.
    """
    tables = [
        "shopping_list_items",
        "shopping_lists",
        "inventory_reservations",
        "planned_meals",
        "cycle_slots",
        "meal_slot_definitions",
        "meal_cycles",
        "meal_tags",
        "meal_meal_types",
        "meal_recipes",
        "meals",
        "recipe_dependencies",
        "recipe_outputs",
        "recipe_variant_ingredient_overrides",
        "recipe_variants",
        "recipe_ingredient_substitutions",
        "recipe_advance_prep",
        "recipe_equipment",
        "recipe_ingredients",
        "recipe_prep_groups",
        "recipe_tags",
        "recipe_meal_types",
        "recipes",
        "inventory_transactions",
        "inventory_lots",
        "equipment",
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
    # id, name, shopping category, preferred unit, default location, perishable,
    # staple enabled, staple minimum, staple target, staple unit
    ingredients = [
        (1, "Chicken Breast", 2, 2, 3, True, False, None, None, None),
        (2, "Ground Beef", 2, 2, 3, True, False, None, None, None),
        (3, "Eggs", 3, 14, 2, True, True, 6, 18, 14),
        (4, "Milk", 3, 8, 2, True, True, 1, 2, 8),
        (5, "Cheddar Cheese", 3, 1, 2, True, False, None, None, None),
        (6, "Rice", 6, 8, 1, False, True, 2, 6, 8),
        (7, "Pasta", 6, 2, 1, False, True, 1, 4, 2),
        (8, "Tomato Sauce", 6, 8, 1, False, False, None, None, None),
        (9, "Bell Pepper", 1, 14, 2, True, False, None, None, None),
        (10, "Onion", 1, 14, 1, True, True, 2, 6, 14),
        (11, "Potatoes", 1, 2, 1, True, False, None, None, None),
        (12, "Tortillas", 4, 14, 1, False, True, 8, 24, 14),
        (13, "Black Beans", 6, 14, 1, False, True, 2, 8, 14),
        (14, "Bread", 4, 14, 1, False, True, 4, 12, 14),
        (15, "Butter", 3, 1, 2, True, True, 8, 16, 1),
        (16, "Garlic", 1, 14, 1, True, True, 4, 12, 14),
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
        connection.execute(text("UPDATE households SET name='Test Household', default_servings=4 WHERE id=1"))
        connection.execute(text("INSERT INTO tags (id, household_id, name, normalized_name, category, active) VALUES (1,1,'Quick','quick','STYLE',1),(2,1,'Family Favorite','family favorite','STYLE',1),(3,1,'Freezer Friendly','freezer friendly','STYLE',1),(4,1,'Weeknight','weeknight','STYLE',1)"))

        for ingredient_id, name, category_id, unit_id, location_id, perishable, staple_enabled, staple_minimum, staple_target, staple_unit_id in ingredients:
            connection.execute(
                text("""
                    INSERT INTO ingredients
                    (id, household_id, name, normalized_name, shopping_category_id, preferred_unit_id,
                     default_location_id, perishable, staple_enabled, staple_minimum, staple_target,
                     staple_unit_id, active, notes)
                    VALUES (:id, 1, :name, :normalized, :category, :unit, :location, :perishable,
                            :staple_enabled, :staple_minimum, :staple_target, :staple_unit, 1,
                            'Seeded test ingredient with advanced inventory defaults')
                """),
                {
                    "id": ingredient_id,
                    "name": name,
                    "normalized": name.casefold(),
                    "category": category_id,
                    "unit": unit_id,
                    "location": location_id,
                    "perishable": perishable,
                    "staple_enabled": staple_enabled,
                    "staple_minimum": staple_minimum,
                    "staple_target": staple_target,
                    "staple_unit": staple_unit_id,
                },
            )

        connection.execute(text("INSERT INTO ingredient_aliases (ingredient_id, alias, normalized_alias) VALUES (10,'Yellow Onion','yellow onion'),(16,'Garlic Clove','garlic clove')"))
        connection.execute(text("""
            INSERT INTO equipment (id, household_id, name, normalized_name, category, notes, active) VALUES
            (1,1,'12-inch Skillet','12-inch skillet','COOKWARE','Seeded skillet',1),
            (2,1,'Large Pot','large pot','COOKWARE','For pasta and rice',1),
            (3,1,'Sheet Pan','sheet pan','BAKEWARE','Seeded sheet pan',1),
            (4,1,'Blender','blender','APPLIANCE','Seeded blender',1)
        """))

        recipe_ingredient_id = 1
        recipe_ingredient_ids: dict[tuple[int, int], int] = {}
        for recipe_id, name, description, meal_type, cook_minutes, recipe_ingredients in recipes:
            connection.execute(
                text("""
                    INSERT INTO recipes
                    (id, household_id, name, normalized_name, description, base_servings, serving_unit,
                     yield_quantity, yield_unit_id, prep_time_minutes, cook_time_minutes, notes, favorite, active)
                    VALUES (:id, 1, :name, :normalized, :description, 4, 'servings',
                            :yield_quantity, :yield_unit, 10, :cook, 'Seeded recipe notes', :favorite, 1)
                """),
                {
                    "id": recipe_id,
                    "name": name,
                    "normalized": name.casefold(),
                    "description": description,
                    "cook": cook_minutes,
                    "favorite": recipe_id in (1, 2, 4),
                    "yield_quantity": 4 if recipe_id in (1, 3) else None,
                    "yield_unit": 14 if recipe_id in (1, 3) else None,
                },
            )
            connection.execute(text("INSERT INTO recipe_meal_types (recipe_id, meal_type) VALUES (:id, :meal_type)"), {"id": recipe_id, "meal_type": meal_type})
            connection.execute(text("INSERT INTO recipe_tags (recipe_id, tag_id) VALUES (:id, :tag_id)"), {"id": recipe_id, "tag_id": 1 if recipe_id in (2, 4, 5, 7, 9, 12) else 4})
            connection.execute(text("INSERT INTO recipe_prep_groups (id, recipe_id, name, sort_order) VALUES (:id,:recipe,'Main prep',0)"), {"id": recipe_id, "recipe": recipe_id})
            for sort_order, (ingredient_id, quantity, unit_id) in enumerate(recipe_ingredients):
                connection.execute(
                    text("""
                        INSERT INTO recipe_ingredients
                        (id, recipe_id, ingredient_id, prep_group_id, quantity, unit_id, display_text,
                         preparation, prep_method, prep_size, prep_state, optional, scaling_mode,
                         required_state, sort_order, notes)
                        VALUES (:id, :recipe, :ingredient, :prep_group, :quantity, :unit, :display_text,
                                :preparation, :prep_method, :prep_size, :prep_state, 0, :scaling_mode,
                                :required_state, :sort_order, :notes)
                    """),
                    {
                        "id": recipe_ingredient_id,
                        "recipe": recipe_id,
                        "ingredient": ingredient_id,
                        "prep_group": recipe_id,
                        "quantity": quantity,
                        "unit": unit_id,
                        "display_text": f"Seeded ingredient {ingredient_id}",
                        "preparation": "Prepare as directed",
                        "prep_method": "CHOP" if ingredient_id in (9, 10, 16) else "MEASURE",
                        "prep_size": "diced" if ingredient_id in (9, 10) else None,
                        "prep_state": "fresh" if ingredient_id in (1, 2, 9, 10, 16) else "pantry",
                        "scaling_mode": "FIXED" if recipe_id == 2 and sort_order == 1 else "LINEAR",
                        "required_state": "THAWED" if ingredient_id in (1, 2) else "ANY",
                        "sort_order": sort_order,
                        "notes": "Seeded structured prep metadata",
                    },
                )
                recipe_ingredient_ids[(recipe_id, ingredient_id)] = recipe_ingredient_id
                recipe_ingredient_id += 1

        connection.execute(text("INSERT INTO recipe_prep_groups (id, recipe_id, name, sort_order) VALUES (101,1,'Rice prep',1)"))
        connection.execute(text("UPDATE recipe_ingredients SET prep_group_id=101 WHERE id=:id"), {"id": recipe_ingredient_ids[(1, 6)]})
        connection.execute(text("""
            INSERT INTO recipe_advance_prep (id, recipe_id, prep_group_id, title, lead_time_minutes, duration_minutes, instructions, sort_order) VALUES
            (1,1,101,'Rinse rice',30,5,'Rinse until water runs mostly clear.',0),
            (2,2,NULL,'Thaw ground beef',480,5,'Move beef to refrigerator the morning of cooking.',0)
        """))
        connection.execute(text("""
            INSERT INTO recipe_equipment (id, recipe_id, equipment_id, quantity, notes, sort_order) VALUES
            (1,1,1,1,'Brown chicken',0),(2,1,2,1,'Cook rice',1),(3,3,2,1,'Boil pasta',0),(4,6,3,1,'Bake potatoes',0)
        """))

        beef_taco_beef_id = recipe_ingredient_ids[(2, 2)]
        connection.execute(text("""
            INSERT INTO recipe_ingredient_substitutions
            (id, recipe_ingredient_id, substitute_ingredient_id, ratio, preferred, notes, sort_order)
            VALUES (1,:recipe_ingredient,1,1.000000,0,'Use chicken for a lighter taco variant',0)
        """), {"recipe_ingredient": beef_taco_beef_id})
        connection.execute(text("""
            INSERT INTO recipe_variants (id, recipe_id, name, normalized_name, notes, active, sort_order)
            VALUES (1,2,'Chicken Taco Night','chicken taco night','Seeded variant using saved substitution',1,0)
        """))
        connection.execute(text("""
            INSERT INTO recipe_variant_ingredient_overrides
            (id, variant_id, recipe_ingredient_id, quantity, unit_id, substitution_id,
             preparation, prep_method, prep_size, prep_state, notes)
            VALUES (1,1,:recipe_ingredient,NULL,NULL,1,NULL,NULL,NULL,NULL,'Use substitution #1')
        """), {"recipe_ingredient": beef_taco_beef_id})
        connection.execute(text("""
            INSERT INTO recipe_outputs (id, recipe_id, name, normalized_name, quantity, unit_id, notes, active, sort_order)
            VALUES (1,1,'Cooked Chicken','cooked chicken',1.000000,2,'Prepared component for later meals',1,0)
        """))
        connection.execute(text("""
            INSERT INTO recipe_dependencies
            (id, recipe_id, recipe_output_id, quantity, unit_id, scaling_mode, notes, sort_order)
            VALUES (1,8,1,1.000000,2,'LINEAR','Use cooked chicken output from Chicken and Rice',0)
        """))

        for meal_id, name, description, meal_type, recipe_id in meals:
            connection.execute(
                text("""
                    INSERT INTO meals (id, household_id, name, normalized_name, description, favorite, active)
                    VALUES (:id, 1, :name, :normalized, :description, :favorite, 1)
                """),
                {"id": meal_id, "name": name, "normalized": name.casefold(), "description": description, "favorite": meal_id in (1, 2, 4)},
            )
            connection.execute(text("INSERT INTO meal_meal_types (meal_id, meal_type) VALUES (:id, :meal_type)"), {"id": meal_id, "meal_type": meal_type})
            connection.execute(text("INSERT INTO meal_recipes (id, meal_id, recipe_id, serving_multiplier, default_servings, sort_order, notes) VALUES (:id, :meal, :recipe, 1, 4, 0, 'Seeded Meal component')"), {"id": meal_id, "meal": meal_id, "recipe": recipe_id})

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
                    (id, household_id, ingredient_id, location_id, quantity, unit_id, purchase_date,
                     opened_date, expiration_date, frozen_date, thawed_date, notes)
                    VALUES (:id, 1, :ingredient, :location, :quantity, :unit, :purchase,
                            :opened, :expiration, :frozen, :thawed, 'Seeded test inventory with lot state')
                """),
                {
                    "id": lot_id,
                    "ingredient": ingredient_id,
                    "location": location_id,
                    "quantity": quantity,
                    "unit": unit_id,
                    "purchase": today - timedelta(days=lot_id % 7),
                    "opened": today - timedelta(days=1) if lot_id in (4, 5, 8, 15) else None,
                    "expiration": expiration,
                    "frozen": today - timedelta(days=10) if lot_id in (1, 2) else None,
                    "thawed": today - timedelta(days=1) if lot_id == 1 else None,
                },
            )
            connection.execute(
                text("""
                    INSERT INTO inventory_transactions
                    (household_id, lot_id, transaction_type, quantity_delta, unit_id, to_location_id, note)
                    VALUES (1, :lot, 'PURCHASE', :quantity, :unit, :location, 'Seeded test data')
                """),
                {"lot": lot_id, "quantity": quantity, "unit": unit_id, "location": location_id},
            )

        connection.execute(text("""
            INSERT INTO meal_cycles
            (id, household_id, name, normalized_name, duration_days, status, start_date, notes, population_rules, smart_preferences)
            VALUES (1,1,'Sample Week','sample week',7,'DRAFT',:start_date,'Seeded cycle for placement testing','{}',:preferences)
        """), {
            "start_date": today,
            "preferences": json.dumps({"repeat_spacing_days": 2, "favorite_weight": 2, "history_penalty": 0.5}),
        })
        slot_definitions = [
            (1, "Breakfast", 0, "08:00:00"),
            (2, "Lunch", 1, "12:30:00"),
            (3, "Dinner", 2, "18:30:00"),
        ]
        for definition_id, label, sort_order, serving_time in slot_definitions:
            connection.execute(
                text("INSERT INTO meal_slot_definitions (id, cycle_id, label, sort_order, serving_time) VALUES (:id,1,:label,:sort_order,:serving_time)"),
                {"id": definition_id, "label": label, "sort_order": sort_order, "serving_time": serving_time},
            )
        slot_id = 1
        for day_number in range(1, 8):
            for definition_id, _label, sort_order, _serving_time in slot_definitions:
                connection.execute(text("INSERT INTO cycle_slots (id, cycle_id, slot_definition_id, day_number, sort_order) VALUES (:id,1,:definition,:day,:sort_order)"), {"id": slot_id, "definition": definition_id, "day": day_number, "sort_order": sort_order})
                slot_id += 1

        chicken_scaled = [{
            "meal_recipe_id": 1,
            "recipe_id": 1,
            "recipe_name": "Chicken and Rice",
            "servings": "4",
            "ingredients": [
                {"recipe_ingredient_id": recipe_ingredient_ids[(1, 1)], "ingredient_id": 1, "quantity": "1", "unit_id": 2, "manual_review": False},
                {"recipe_ingredient_id": recipe_ingredient_ids[(1, 6)], "ingredient_id": 6, "quantity": "2", "unit_id": 8, "manual_review": False},
                {"recipe_ingredient_id": recipe_ingredient_ids[(1, 10)], "ingredient_id": 10, "quantity": "1", "unit_id": 14, "manual_review": False},
            ],
        }]
        connection.execute(text("""
            INSERT INTO planned_meals
            (id, cycle_slot_id, meal_id, locked, planned_servings, planned_leftover_servings,
             component_serving_overrides, scaled_components, snapshot_name, snapshot_description,
             snapshot_meal_types, snapshot_components)
            VALUES (1,3,1,1,4,1,'{}',:scaled,'Chicken Dinner','Chicken and rice dinner','["DINNER"]',:components)
        """), {
            "scaled": json.dumps(chicken_scaled),
            "components": json.dumps([{"meal_recipe_id": 1, "recipe_id": 1, "recipe_name": "Chicken and Rice", "serving_multiplier": "1", "default_servings": "4"}]),
        })

        connection.execute(text("""
            INSERT INTO inventory_reservations
            (id, household_id, cycle_id, planned_meal_id, meal_recipe_id, recipe_id,
             recipe_ingredient_id, ingredient_id, quantity, unit_id, status)
            VALUES
            (1,1,1,1,1,1,:chicken_ri,1,1.000000,2,'ACTIVE'),
            (2,1,1,1,1,1,:rice_ri,6,2.000000,8,'ACTIVE'),
            (3,1,1,1,1,1,:onion_ri,10,1.000000,14,'ACTIVE')
        """), {
            "chicken_ri": recipe_ingredient_ids[(1, 1)],
            "rice_ri": recipe_ingredient_ids[(1, 6)],
            "onion_ri": recipe_ingredient_ids[(1, 10)],
        })

    print(f"Reset test database: {TEST_DB}" if reset else f"Created test database: {TEST_DB}")
    print("Seeded: 16 ingredients, 12 recipes, 12 meals, 4 equipment items, 16 inventory lots, advanced recipe data, reservations, scheduled serving times, and 1 seven-day cycle")
    return TEST_DB


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or reset the Cycle Meal Planner test database.")
    parser.add_argument("--reset", action="store_true", help="Clear and rebuild seeded test data in place.")
    args = parser.parse_args()
    seed(reset=args.reset)


if __name__ == "__main__":
    main()
