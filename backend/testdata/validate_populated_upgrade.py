from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, text

BACKEND_DIR = Path(__file__).resolve().parents[1]
DB_PATH = Path(__file__).with_name("migration-upgrade-test.db").resolve()


def alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini")); config.set_main_option("script_location", str(BACKEND_DIR / "migrations")); return config


def _columns(connection, table: str) -> set[str]:
    return {item[1] for item in connection.execute(text(f"PRAGMA table_info({table})"))}


def main() -> None:
    if DB_PATH.exists(): DB_PATH.unlink()
    database_url = f"sqlite:///{DB_PATH.as_posix()}"; os.environ["CYCLE_MEAL_PLANNER_DATABASE_URL"] = database_url; os.environ["CYCLE_MEAL_PLANNER_ENV"] = "migration-upgrade-test"
    command.upgrade(alembic_config(), "0020_inventory_reservations"); engine = create_engine(database_url)

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor(); cursor.execute("PRAGMA foreign_keys=ON"); cursor.close()

    with engine.begin() as connection:
        location_id = connection.execute(text("SELECT id FROM inventory_locations ORDER BY id LIMIT 1")).scalar_one(); unit_id = connection.execute(text("SELECT id FROM measurement_units ORDER BY id LIMIT 1")).scalar_one(); unit_family = connection.execute(text("SELECT unit_family FROM measurement_units WHERE id=:id"), {"id": unit_id}).scalar_one()
        connection.execute(text("INSERT INTO ingredients (id, household_id, name, normalized_name, perishable, active, notes) VALUES (9001,1,'Migration Test Ingredient','migration test ingredient',0,1,'must survive upgrade')")); connection.execute(text("INSERT INTO ingredient_aliases (id, ingredient_id, alias, normalized_alias) VALUES (9001,9001,'Migration Alias','migration alias')")); connection.execute(text("INSERT INTO recipes (id, household_id, name, normalized_name, base_servings, serving_unit, favorite, active) VALUES (9001,1,'Migration Recipe','migration recipe',4,'servings',0,1)")); connection.execute(text("INSERT INTO recipe_advance_prep (id, recipe_id, prep_group_id, title, lead_time_minutes, duration_minutes, instructions, sort_order) VALUES (9001,9001,NULL,'Legacy prep task',60,10,'must survive',0)")); connection.execute(text("INSERT INTO meal_cycles (id, household_id, name, normalized_name, duration_days, status, start_date, notes, population_rules, smart_preferences) VALUES (9001,1,'Migration Cycle','migration cycle',1,'DRAFT','2026-09-01','must survive upgrade','{}','{}')")); connection.execute(text("INSERT INTO meal_slot_definitions (id, cycle_id, label, sort_order) VALUES (9001,9001,'Dinner',0)")); connection.execute(text("INSERT INTO cycle_slots (id, cycle_id, slot_definition_id, day_number, sort_order) VALUES (9001,9001,9001,1,0)")); connection.execute(text("INSERT INTO inventory_lots (id, household_id, ingredient_id, location_id, quantity, unit_id, purchase_date, notes) VALUES (9001,1,9001,:location_id,2,:unit_id,'2026-09-01','legacy shopping purchase lot')"), {"location_id": location_id, "unit_id": unit_id}); connection.execute(text("INSERT INTO shopping_lists (id, household_id, meal_cycle_id, generated_at) VALUES (9001,1,9001,'2026-09-01 12:00:00')")); connection.execute(text("""INSERT INTO shopping_list_items (id,shopping_list_id,ingredient_id,shopping_category_id,unit_id,unit_family,required_quantity,inventory_quantity,generated_quantity,adjustment_quantity,source_trace,warning,status,actual_quantity,actual_unit_id,purchase_date,storage_location_id,expiration_date,purchase_notes,inventory_lot_id,completed_at) VALUES (9001,9001,9001,NULL,:unit_id,:unit_family,2,0,2,0,'[]',NULL,'COMPLETED',2,:unit_id,'2026-09-01',:location_id,NULL,'legacy completed purchase',9001,'2026-09-01 12:30:00')"""), {"unit_id": unit_id, "unit_family": unit_family, "location_id": location_id})

    command.upgrade(alembic_config(), "head")
    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one(); row = connection.execute(text("SELECT name, staple_enabled, staple_minimum, staple_target, staple_unit_id FROM ingredients WHERE id=9001")).one(); alias_count = connection.execute(text("SELECT COUNT(*) FROM ingredient_aliases WHERE ingredient_id=9001")).scalar_one(); slot = connection.execute(text("SELECT label, serving_time FROM meal_slot_definitions WHERE id=9001")).one(); cycle = connection.execute(text("SELECT status,lifecycle_status,activated_at,completed_at,cancelled_at FROM meal_cycles WHERE id=9001")).one(); prep = connection.execute(text("SELECT title,task_type,reminder_enabled,reminder_offset_minutes FROM recipe_advance_prep WHERE id=9001")).one(); planned_info = {item[1]: item for item in connection.execute(text("PRAGMA table_info(planned_meals)"))}; leftover_info = {item[1]: item for item in connection.execute(text("PRAGMA table_info(leftovers)"))}; purchase_columns = _columns(connection, "shopping_item_purchases"); shopping_columns = _columns(connection, "shopping_list_items"); revision_columns = _columns(connection, "planned_meal_revisions"); transaction_columns = _columns(connection, "inventory_transactions"); transaction_sql = connection.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name='inventory_transactions'")).scalar_one(); purchase_row = connection.execute(text("SELECT shopping_list_item_id,actual_quantity,actual_unit_id,purchased_ingredient_id,satisfied_quantity,satisfied_unit_id,purchase_kind,inventory_lot_id,purchase_notes FROM shopping_item_purchases WHERE shopping_list_item_id=9001")).one(); shopping_row = connection.execute(text("SELECT required_quantity,baseline_required_quantity,plan_delta_quantity,purchased_excess_quantity FROM shopping_list_items WHERE id=9001")).one(); serving_unit = connection.execute(text("SELECT code,unit_family FROM measurement_units WHERE id=16")).one(); fk_violations = connection.execute(text("PRAGMA foreign_key_check")).all()
        required_tables = {"gather_lot_selections", "recipe_cooking_steps", "recipe_cooking_timers", "planned_cooking_timers", "recipe_cooking_step_equipment", "recipe_cooking_temperatures", "recipe_cooking_coordination", "recipe_cooking_dependencies", "meal_completions", "meal_completion_usage", "meal_completion_allocations", "meal_completion_outputs", "production_coverage_reservations"}; existing_tables = {item[0] for item in connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}

    assert version == "0038_inventory_waste_spoilage"; assert row.name == "Migration Test Ingredient"; assert bool(row.staple_enabled) is False; assert row.staple_minimum is None and row.staple_target is None and row.staple_unit_id is None; assert alias_count == 1; assert slot.label == "Dinner" and slot.serving_time is None; assert cycle.status == "DRAFT" and cycle.lifecycle_status == "DRAFT" and cycle.activated_at is None and cycle.completed_at is None and cycle.cancelled_at is None; assert prep.title == "Legacy prep task" and prep.task_type == "PREP" and bool(prep.reminder_enabled) is False; assert required_tables.issubset(existing_tables); assert planned_info["meal_id"][3] == 0 and "source_recipe_id" in planned_info; assert leftover_info["source_meal_id"][3] == 0 and "source_recipe_id" in leftover_info
    assert {"baseline_required_quantity","plan_delta_quantity","purchased_excess_quantity"}.issubset(shopping_columns); assert {"shopping_list_item_id","actual_quantity","actual_unit_id","purchased_ingredient_id","satisfied_quantity","satisfied_unit_id","purchase_kind","idempotency_key","inventory_lot_id","completed_at"}.issubset(purchase_columns); assert {"cycle_id","cycle_slot_id","planned_meal_id","action","source_type","planned_servings","scaled_components","changed_at"}.issubset(revision_columns); assert "reason" in transaction_columns; assert "WASTE" in transaction_sql and "SPOILAGE" in transaction_sql
    assert shopping_row.required_quantity == 2 and shopping_row.baseline_required_quantity == 2 and shopping_row.plan_delta_quantity == 0 and shopping_row.purchased_excess_quantity == 0; assert purchase_row.shopping_list_item_id == 9001 and purchase_row.actual_quantity == 2 and purchase_row.purchased_ingredient_id == 9001 and purchase_row.satisfied_quantity == 2 and purchase_row.satisfied_unit_id == purchase_row.actual_unit_id and purchase_row.purchase_kind == "STANDARD" and purchase_row.inventory_lot_id == 9001 and purchase_row.purchase_notes == "legacy completed purchase"; assert serving_unit.code == "serving" and serving_unit.unit_family == "SERVING"; assert fk_violations == []
    engine.dispose(); DB_PATH.unlink(missing_ok=True); print("Populated SQLite upgrade 0020 -> 0038 succeeded, preserved existing data, backfilled Shopping purchase provenance, and added WASTE/SPOILAGE transaction support.")


if __name__ == "__main__": main()
