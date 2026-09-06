from __future__ import annotations

import argparse
import json
from datetime import date

from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

try:
    from testdata.seed_test_db import configure_database
except ModuleNotFoundError:
    from seed_test_db import configure_database

CYCLE_ID = 9501
CYCLE_NAME = "Shopping Partial + Substitution Test Cycle"
SLOT_ID = 9501
PLANNED_ID = 9501
RECIPE_ID = 9501
PARTIAL_INGREDIENT_ID = 9501
ORIGINAL_INGREDIENT_ID = 9502
SUBSTITUTE_INGREDIENT_ID = 9503
PARTIAL_NAME = "UAT Partial Apples"
ORIGINAL_NAME = "UAT Original Flour"
SUBSTITUTE_NAME = "UAT Substitute Bags"


def _configure() -> None:
    configure_database()
    from app.database.migrations import run_migrations
    run_migrations()


def _cleanup(connection) -> None:
    purchase_lot_ids = [int(row[0]) for row in connection.execute(text("""
        SELECT sip.inventory_lot_id
        FROM shopping_item_purchases sip
        JOIN shopping_list_items sli ON sli.id=sip.shopping_list_item_id
        JOIN shopping_lists sl ON sl.id=sli.shopping_list_id
        WHERE sl.meal_cycle_id=:cycle
    """), {"cycle": CYCLE_ID})]
    lot_csv = ",".join(str(value) for value in purchase_lot_ids) or "-1"

    connection.execute(text("DELETE FROM inventory_reservations WHERE cycle_id=:cycle"), {"cycle": CYCLE_ID})
    connection.execute(text("""
        DELETE FROM shopping_item_purchases WHERE shopping_list_item_id IN
        (SELECT sli.id FROM shopping_list_items sli JOIN shopping_lists sl ON sl.id=sli.shopping_list_id WHERE sl.meal_cycle_id=:cycle)
    """), {"cycle": CYCLE_ID})
    connection.execute(text("DELETE FROM shopping_list_items WHERE shopping_list_id IN (SELECT id FROM shopping_lists WHERE meal_cycle_id=:cycle)"), {"cycle": CYCLE_ID})
    connection.execute(text("DELETE FROM shopping_lists WHERE meal_cycle_id=:cycle"), {"cycle": CYCLE_ID})
    connection.execute(text(f"DELETE FROM inventory_transactions WHERE lot_id IN ({lot_csv})"))
    connection.execute(text(f"DELETE FROM inventory_lots WHERE id IN ({lot_csv})"))
    connection.execute(text("DELETE FROM planned_meals WHERE id=:planned"), {"planned": PLANNED_ID})
    connection.execute(text("DELETE FROM cycle_slots WHERE cycle_id=:cycle"), {"cycle": CYCLE_ID})
    connection.execute(text("DELETE FROM meal_slot_definitions WHERE cycle_id=:cycle"), {"cycle": CYCLE_ID})
    connection.execute(text("DELETE FROM meal_cycles WHERE id=:cycle"), {"cycle": CYCLE_ID})
    connection.execute(text("DELETE FROM recipe_ingredients WHERE recipe_id=:recipe"), {"recipe": RECIPE_ID})
    connection.execute(text("DELETE FROM recipe_meal_types WHERE recipe_id=:recipe"), {"recipe": RECIPE_ID})
    connection.execute(text("DELETE FROM recipes WHERE id=:recipe"), {"recipe": RECIPE_ID})
    connection.execute(text("DELETE FROM ingredient_aliases WHERE ingredient_id IN (:partial,:original,:substitute)"), {
        "partial": PARTIAL_INGREDIENT_ID, "original": ORIGINAL_INGREDIENT_ID, "substitute": SUBSTITUTE_INGREDIENT_ID,
    })
    connection.execute(text("DELETE FROM ingredients WHERE id IN (:partial,:original,:substitute)"), {
        "partial": PARTIAL_INGREDIENT_ID, "original": ORIGINAL_INGREDIENT_ID, "substitute": SUBSTITUTE_INGREDIENT_ID,
    })


def seed_fixture() -> None:
    _configure()
    from app.api.shopping import _regenerate
    from app.database.session import SessionLocal, engine
    from app.models.meal_cycle import CycleSlot, MealCycle

    with engine.begin() as connection:
        _cleanup(connection)
        each_id = int(connection.execute(text("SELECT id FROM measurement_units WHERE code='each'")).scalar_one())
        lb_id = int(connection.execute(text("SELECT id FROM measurement_units WHERE code='lb'")).scalar_one())
        pantry_location = int(connection.execute(text("SELECT id FROM inventory_locations WHERE household_id=1 AND name='Pantry'")).scalar_one())
        pantry_category = connection.execute(text("SELECT id FROM shopping_categories WHERE household_id=1 AND name='Pantry'")).scalar_one_or_none()

        for ingredient_id, name, normalized, unit_id in [
            (PARTIAL_INGREDIENT_ID, PARTIAL_NAME, "uat partial apples", each_id),
            (ORIGINAL_INGREDIENT_ID, ORIGINAL_NAME, "uat original flour", lb_id),
            (SUBSTITUTE_INGREDIENT_ID, SUBSTITUTE_NAME, "uat substitute bags", each_id),
        ]:
            connection.execute(text("""
                INSERT INTO ingredients
                (id, household_id, name, normalized_name, shopping_category_id, preferred_unit_id,
                 default_location_id, perishable, active, notes)
                VALUES (:id,1,:name,:normalized,:category,:unit,:location,0,1,
                        'Deterministic Shopping partial/substitution UAT fixture')
            """), {"id": ingredient_id, "name": name, "normalized": normalized, "category": pantry_category, "unit": unit_id, "location": pantry_location})

        connection.execute(text("""
            INSERT INTO recipes
            (id, household_id, name, normalized_name, description, base_servings, serving_unit,
             prep_time_minutes, cook_time_minutes, favorite, active)
            VALUES (:id,1,'Shopping UAT Recipe','shopping uat recipe',
                    'Deterministic partial purchase and substitution UAT Recipe',4,'servings',0,0,0,1)
        """), {"id": RECIPE_ID})
        connection.execute(text("INSERT INTO recipe_meal_types (recipe_id, meal_type) VALUES (:recipe,'DINNER')"), {"recipe": RECIPE_ID})
        connection.execute(text("""
            INSERT INTO recipe_ingredients
            (id, recipe_id, ingredient_id, quantity, unit_id, optional, scaling_mode, required_state, sort_order)
            VALUES
            (9501,:recipe,:partial,4,:each,0,'LINEAR','ANY',0),
            (9502,:recipe,:original,2,:lb,0,'LINEAR','ANY',1)
        """), {"recipe": RECIPE_ID, "partial": PARTIAL_INGREDIENT_ID, "original": ORIGINAL_INGREDIENT_ID, "each": each_id, "lb": lb_id})

        connection.execute(text("""
            INSERT INTO meal_cycles
            (id, household_id, name, normalized_name, duration_days, status, lifecycle_status,
             start_date, notes, population_rules, smart_preferences)
            VALUES (:id,1,:name,'shopping partial substitution test cycle',1,'DRAFT','DRAFT',:today,
                    'Deterministic v1.0 Shopping partial/substitution UAT fixture','{}','{}')
        """), {"id": CYCLE_ID, "name": CYCLE_NAME, "today": date.today()})
        connection.execute(text("""
            INSERT INTO meal_slot_definitions (id, cycle_id, label, sort_order, serving_time)
            VALUES (:id,:cycle,'Dinner',0,'18:30:00')
        """), {"id": SLOT_ID, "cycle": CYCLE_ID})
        connection.execute(text("INSERT INTO cycle_slots (id, cycle_id, slot_definition_id, day_number, sort_order) VALUES (:id,:cycle,:definition,1,0)"), {"id": SLOT_ID, "cycle": CYCLE_ID, "definition": SLOT_ID})

        snapshot_components = json.dumps([{
            "meal_recipe_id": -1,
            "recipe_id": RECIPE_ID,
            "serving_multiplier": "1",
            "default_servings": None,
            "sort_order": 0,
            "notes": "Direct Recipe occurrence",
        }])
        scaled_components = json.dumps([{
            "meal_recipe_id": -1,
            "recipe_id": RECIPE_ID,
            "base_servings": "4",
            "requested_servings": "4",
            "scale_factor": "1",
            "ingredients": [
                {"recipe_ingredient_id": 9501, "ingredient_id": PARTIAL_INGREDIENT_ID, "quantity": "4", "unit_id": each_id, "scaling_mode": "LINEAR", "manual_review": False},
                {"recipe_ingredient_id": 9502, "ingredient_id": ORIGINAL_INGREDIENT_ID, "quantity": "2", "unit_id": lb_id, "scaling_mode": "LINEAR", "manual_review": False},
            ],
        }])
        connection.execute(text("""
            INSERT INTO planned_meals
            (id, cycle_slot_id, meal_id, source_type, source_recipe_id, locked,
             planned_servings, planned_leftover_servings, component_serving_overrides,
             scaled_components, snapshot_name, snapshot_description, snapshot_meal_types, snapshot_components)
            VALUES (:id,:slot,NULL,'DIRECT_RECIPE',:recipe,0,4,0,'{}',:scaled,'Shopping UAT Recipe',
                    'Deterministic Shopping partial/substitution UAT occurrence','["DINNER"]',:components)
        """), {"id": PLANNED_ID, "slot": SLOT_ID, "recipe": RECIPE_ID, "scaled": scaled_components, "components": snapshot_components})

    with SessionLocal() as db:
        cycle = db.scalar(
            select(MealCycle)
            .where(MealCycle.id == CYCLE_ID)
            .options(selectinload(MealCycle.slots).selectinload(CycleSlot.planned_meal))
        )
        _regenerate(db, cycle)

    print(f"Shopping UAT fixture ready: {CYCLE_NAME} (ID {CYCLE_ID})")
    print(f"Partial item: {PARTIAL_NAME} = 4 each")
    print(f"Substitution source: {ORIGINAL_NAME} = 2 lb")
    print(f"Substitution target available in Ingredient picker: {SUBSTITUTE_NAME} (preferred unit each)")


def verify_fixture() -> None:
    _configure()
    from app.database.session import engine
    with engine.connect() as connection:
        rows = connection.execute(text("""
            SELECT sli.ingredient_id, i.name, sli.status, sli.required_quantity, sli.generated_quantity,
                   COUNT(sip.id) AS purchase_count,
                   COALESCE(SUM(CASE WHEN sip.purchase_kind='SUBSTITUTION' THEN sip.satisfied_quantity ELSE 0 END),0) AS substitution_satisfied
            FROM shopping_list_items sli
            JOIN shopping_lists sl ON sl.id=sli.shopping_list_id
            JOIN ingredients i ON i.id=sli.ingredient_id
            LEFT JOIN shopping_item_purchases sip ON sip.shopping_list_item_id=sli.id
            WHERE sl.meal_cycle_id=:cycle AND sli.ingredient_id IN (:partial,:original)
            GROUP BY sli.id, sli.ingredient_id, i.name, sli.status, sli.required_quantity, sli.generated_quantity
            ORDER BY sli.ingredient_id
        """), {"cycle": CYCLE_ID, "partial": PARTIAL_INGREDIENT_ID, "original": ORIGINAL_INGREDIENT_ID}).mappings().all()
        purchases = connection.execute(text("""
            SELECT sip.purchase_kind, src.name AS original_name, bought.name AS purchased_name,
                   sip.actual_quantity, au.code AS actual_unit, sip.satisfied_quantity, su.code AS satisfied_unit,
                   sip.inventory_lot_id
            FROM shopping_item_purchases sip
            JOIN shopping_list_items sli ON sli.id=sip.shopping_list_item_id
            JOIN shopping_lists sl ON sl.id=sli.shopping_list_id
            JOIN ingredients src ON src.id=sli.ingredient_id
            JOIN ingredients bought ON bought.id=sip.purchased_ingredient_id
            JOIN measurement_units au ON au.id=sip.actual_unit_id
            JOIN measurement_units su ON su.id=sip.satisfied_unit_id
            WHERE sl.meal_cycle_id=:cycle
            ORDER BY sip.id
        """), {"cycle": CYCLE_ID}).mappings().all()

    for row in rows:
        print(f"{row['name']}: status={row['status']} required={row['required_quantity']} generated={row['generated_quantity']} purchases={row['purchase_count']}")
    for purchase in purchases:
        print(
            f"Purchase: {purchase['purchase_kind']} original={purchase['original_name']} "
            f"bought={purchase['purchased_name']} {purchase['actual_quantity']} {purchase['actual_unit']} "
            f"satisfies={purchase['satisfied_quantity']} {purchase['satisfied_unit']} lot={purchase['inventory_lot_id']}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed deterministic Shopping partial-purchase/substitution UAT data.")
    parser.add_argument("--verify", action="store_true", help="Print persisted Shopping purchase/provenance state.")
    args = parser.parse_args()
    if args.verify:
        verify_fixture()
    else:
        seed_fixture()


if __name__ == "__main__":
    main()
