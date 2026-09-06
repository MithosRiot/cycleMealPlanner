from __future__ import annotations
import os
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, text
HEAD_REVISION = "0038_inventory_waste_spoilage"

def _config():
    c=Config("alembic.ini"); c.set_main_option("script_location","migrations"); return c

def _env(url):
    old=(os.environ.get("CYCLE_MEAL_PLANNER_DATABASE_URL"),os.environ.get("CYCLE_MEAL_PLANNER_ENV")); os.environ["CYCLE_MEAL_PLANNER_DATABASE_URL"]=url; os.environ["CYCLE_MEAL_PLANNER_ENV"]="migration-recovery-test"; return old

def _restore(old):
    for k,v in zip(("CYCLE_MEAL_PLANNER_DATABASE_URL","CYCLE_MEAL_PLANNER_ENV"),old):
        if v is None: os.environ.pop(k,None)
        else: os.environ[k]=v

def _engine(url):
    e=create_engine(url)
    @event.listens_for(e,"connect")
    def fk(conn,_): cur=conn.cursor(); cur.execute("PRAGMA foreign_keys=ON"); cur.close()
    return e

def _inventory(e):
    with e.begin() as c:
        u=c.execute(text("SELECT id FROM measurement_units ORDER BY id LIMIT 1")).scalar_one(); l=c.execute(text("SELECT id FROM inventory_locations ORDER BY id LIMIT 1")).scalar_one(); c.execute(text("INSERT INTO ingredients (id,household_id,name,normalized_name,perishable,active) VALUES (9901,1,'Migration Recovery Ingredient','migration recovery ingredient',0,1)")); c.execute(text("INSERT INTO inventory_lots (id,household_id,ingredient_id,location_id,quantity,unit_id) VALUES (9901,1,9901,:l,5,:u)"),{"l":l,"u":u}); c.execute(text("INSERT INTO inventory_transactions (id,household_id,lot_id,transaction_type,quantity_delta,unit_id,to_location_id) VALUES (9901,1,9901,'MANUAL_ADD',5,:u,:l)"),{"u":u,"l":l})
    return u,l

def _planning(e):
    with e.begin() as c:
        c.execute(text("INSERT INTO meals (id,household_id,name,normalized_name,favorite,active) VALUES (9902,1,'Migration Meal','migration meal',0,1)")); c.execute(text("INSERT INTO meal_cycles (id,household_id,name,normalized_name,duration_days,status,lifecycle_status,start_date,population_rules,smart_preferences) VALUES (9902,1,'Migration Cycle','migration cycle',1,'DRAFT','DRAFT','2026-09-05','{}','{}')")); c.execute(text("INSERT INTO meal_slot_definitions (id,cycle_id,label,sort_order,serving_time) VALUES (9902,9902,'Dinner',0,'18:00:00')")); c.execute(text("INSERT INTO cycle_slots (id,cycle_id,slot_definition_id,day_number,sort_order) VALUES (9902,9902,9902,1,0)")); c.execute(text("INSERT INTO planned_meals (id,cycle_slot_id,meal_id,source_type,locked,planned_servings,planned_leftover_servings,component_serving_overrides,scaled_components,snapshot_name,snapshot_meal_types,snapshot_components) VALUES (9902,9902,9902,'SAVED_MEAL',0,4,1,'{}','[]','Migration Meal','[]','[]')")); c.execute(text("INSERT INTO meal_completions (id,planned_meal_id,status,plan_fingerprint,snapshot_name,snapshot_planned_servings,snapshot_planned_leftover_servings,snapshot_scaled_components,created_at,updated_at) VALUES (9902,9902,'DRAFT',:f,'Migration Meal',4,1,'[]','2026-09-05','2026-09-05')"),{"f":"a"*64}); c.execute(text("INSERT INTO leftovers (id,completion_id,planned_meal_id,source_meal_id,source_meal_name,source_components,actual_servings_produced,actual_servings_eaten,leftover_servings,serving_unit,status,created_at) VALUES (9902,9902,9902,9902,'Migration Meal','[]',5,4,1,'serving','AVAILABLE','2026-09-05')"))

def _assert(e):
    with e.connect() as c:
        assert c.execute(text("PRAGMA foreign_keys")).scalar_one()==1
        assert c.execute(text("SELECT version_num FROM alembic_version")).scalar_one()==HEAD_REVISION
        tables={r[0] for r in c.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        planned={r[1]:r for r in c.execute(text("PRAGMA table_info(planned_meals)"))}
        leftovers={r[1]:r for r in c.execute(text("PRAGMA table_info(leftovers)"))}
        purchases={r[1] for r in c.execute(text("PRAGMA table_info(shopping_item_purchases)"))}
        transactions={r[1] for r in c.execute(text("PRAGMA table_info(inventory_transactions)"))}
        transaction_sql=c.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name='inventory_transactions'")).scalar_one()
        assert c.execute(text("PRAGMA foreign_key_check")).all()==[]
    assert planned["meal_id"][3]==0 and "source_recipe_id" in planned
    assert leftovers["source_meal_id"][3]==0 and "source_recipe_id" in leftovers
    assert {"shopping_item_purchases","planned_meal_revisions","production_coverage_reservations"}.issubset(tables)
    assert not any(x.startswith("_alembic_tmp_") for x in tables)
    assert {"purchased_ingredient_id","satisfied_quantity","satisfied_unit_id","purchase_kind","idempotency_key"}.issubset(purchases)
    assert "reason" in transactions
    assert "WASTE" in transaction_sql and "SPOILAGE" in transaction_sql

def _run(tmp,name,start,partial,planning=False):
    url=f"sqlite:///{(tmp/name).as_posix()}"; old=_env(url)
    try:
        command.upgrade(_config(),start); e=_engine(url); _inventory(e)
        if planning: _planning(e)
        partial(e); command.upgrade(_config(),"head"); _assert(e); e.dispose()
    finally: _restore(old)

def test_0032_recovers_after_partial_sqlite_ddl_with_foreign_keys_and_dependent_rows(tmp_path):
    def p(e):
        with e.begin() as c: c.execute(text("ALTER TABLE meal_completions ADD COLUMN actual_servings_produced NUMERIC(10,3)"))
    _run(tmp_path,"p32.db","0031_meal_completion_finalization",p)

def test_0032_recovers_stale_alembic_batch_table_with_foreign_keys_and_dependent_rows(tmp_path):
    def p(e):
        with e.begin() as c:
            for sql in ["ALTER TABLE meal_completions ADD COLUMN actual_servings_produced NUMERIC(10,3)","ALTER TABLE meal_completions ADD COLUMN actual_servings_eaten NUMERIC(10,3)","ALTER TABLE meal_completions ADD COLUMN production_committed_at DATETIME","ALTER TABLE inventory_lots ADD COLUMN source_type VARCHAR(30)","ALTER TABLE inventory_lots ADD COLUMN source_id INTEGER","ALTER TABLE inventory_lots ADD COLUMN source_name VARCHAR(160)","UPDATE inventory_lots SET source_type='INGREDIENT' WHERE source_type IS NULL","CREATE TABLE _alembic_tmp_inventory_lots AS SELECT * FROM inventory_lots WHERE 0"]: c.execute(text(sql))
    _run(tmp_path,"p32b.db","0031_meal_completion_finalization",p)

def test_0033_recovers_after_partial_additive_sqlite_ddl(tmp_path):
    def p(e):
        with e.begin() as c: c.execute(text("ALTER TABLE planned_meals ADD COLUMN source_type VARCHAR(30) DEFAULT 'SAVED_MEAL' NOT NULL")); c.execute(text("ALTER TABLE planned_meals ADD COLUMN source_origin_planned_meal_id INTEGER"))
    _run(tmp_path,"p33.db","0032_completion_leftovers_outputs",p)

def test_0034_recovers_after_partial_additive_sqlite_ddl_with_foreign_keys_on(tmp_path):
    def p(e):
        with e.begin() as c: c.execute(text("ALTER TABLE meal_cycles ADD COLUMN lifecycle_status VARCHAR(20) DEFAULT 'DRAFT' NOT NULL")); c.execute(text("ALTER TABLE meal_cycles ADD COLUMN activated_at DATETIME"))
    _run(tmp_path,"p34.db","0033_leftover_coverage",p)

def test_0035_recovers_partial_columns_and_stale_batch_with_populated_dependents(tmp_path):
    def p(e):
        with e.begin() as c: c.execute(text("ALTER TABLE planned_meals ADD COLUMN source_recipe_id INTEGER")); c.execute(text("CREATE TABLE _alembic_tmp_planned_meals AS SELECT * FROM planned_meals WHERE 0"))
    _run(tmp_path,"p35.db","0034_cycle_lifecycle",p,True)

def test_0036_recovers_partial_additive_ddl_with_completed_purchase_and_foreign_keys_on(tmp_path):
    url=f"sqlite:///{(tmp_path/'p36.db').as_posix()}"; old=_env(url)
    try:
        command.upgrade(_config(),"0035_direct_recipe_occurrences"); e=_engine(url); u,l=_inventory(e); _planning(e)
        with e.begin() as c:
            c.execute(text("INSERT INTO shopping_lists (id,household_id,meal_cycle_id,generated_at) VALUES (9903,1,9902,'2026-09-05')")); c.execute(text("INSERT INTO shopping_list_items (id,shopping_list_id,ingredient_id,unit_id,unit_family,required_quantity,inventory_quantity,generated_quantity,adjustment_quantity,source_trace,status,actual_quantity,actual_unit_id,purchase_date,storage_location_id,inventory_lot_id,completed_at) VALUES (9903,9903,9901,:u,(SELECT unit_family FROM measurement_units WHERE id=:u),2,0,2,0,'[]','COMPLETED',2,:u,'2026-09-05',:l,9901,'2026-09-05')"),{"u":u,"l":l}); c.execute(text("ALTER TABLE shopping_list_items ADD COLUMN baseline_required_quantity NUMERIC(16,6)")); c.execute(text("UPDATE shopping_list_items SET baseline_required_quantity=required_quantity"))
        command.upgrade(_config(),"head"); _assert(e)
        with e.connect() as c:
            r=c.execute(text("SELECT purchased_ingredient_id,satisfied_quantity,satisfied_unit_id,purchase_kind FROM shopping_item_purchases WHERE shopping_list_item_id=9903")).one(); assert r.purchased_ingredient_id==9901 and r.satisfied_quantity==2 and r.satisfied_unit_id==u and r.purchase_kind=="STANDARD"
        e.dispose()
    finally: _restore(old)
