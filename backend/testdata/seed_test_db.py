from __future__ import annotations

import argparse

from sqlalchemy import text

try:
    from testdata import seed_test_db_base as _base
except ModuleNotFoundError:  # Direct execution from backend/testdata.
    import seed_test_db_base as _base

TEST_DB = _base.TEST_DB
configure_database = _base.configure_database


def _seed_typed_prep_examples() -> None:
    from app.database.session import engine

    with engine.begin() as connection:
        # Existing seeded examples now exercise both the default/general type
        # and a time-sensitive inventory-adjacent type.
        connection.execute(text("UPDATE recipe_advance_prep SET task_type='PREP' WHERE id=1"))
        connection.execute(text("UPDATE recipe_advance_prep SET task_type='THAW' WHERE id=2"))

        # Add a representative MARINATE task to the seeded Chicken and Rice
        # recipe so Meal Plan -> Prep schedule displays multiple typed tasks.
        connection.execute(text("""
            INSERT OR IGNORE INTO recipe_advance_prep
            (id, recipe_id, prep_group_id, task_type, title, lead_time_minutes,
             duration_minutes, instructions, sort_order)
            VALUES
            (3, 1, 1, 'MARINATE', 'Marinate chicken', 120, 10,
             'Season chicken and refrigerate until cooking.', 1)
        """))


def seed(reset: bool = False):
    path = _base.seed(reset=reset)
    _seed_typed_prep_examples()
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the reproducible Cycle Meal Planner test database")
    parser.add_argument("--reset", action="store_true", help="clear and reseed mutable test data")
    args = parser.parse_args()
    seed(reset=args.reset)
    print(TEST_DB)


if __name__ == "__main__":
    main()
