# Seeded Test Database

This directory provides disposable sample data for manual feature testing without touching the normal development database.

The generated SQLite file is `backend/testdata/mealplanner-test.db`. Database files remain gitignored; `seed_test_db.py` recreates the same test database after every pull.

## Start backend with test data

From `backend`:

```powershell
.\.venv\Scripts\python.exe run_test.py
```

If the test database does not exist, it is created automatically. The backend then runs on `http://127.0.0.1:8000` using only the test database.

Seeded data includes:
- 16 ingredients
- 12 recipes
- 12 saved meals covering BREAKFAST, LUNCH, and DINNER
- 16 inventory lots across pantry, refrigerator, and freezer
- 1 seven-day `Sample Week` meal cycle with Breakfast, Lunch, and Dinner slots

## Reset the test database

Stop the backend, then from `backend` run:

```powershell
.\.venv\Scripts\python.exe .\testdata\seed_test_db.py --reset
```

Then start it again with:

```powershell
.\.venv\Scripts\python.exe run_test.py
```

The normal `backend/data/mealplanner.db` is not modified by these commands.
