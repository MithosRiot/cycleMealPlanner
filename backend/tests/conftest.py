import os
from pathlib import Path
import tempfile

TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="cycle-meal-planner-test-"))
os.environ["CYCLE_MEAL_PLANNER_DATA_DIR"] = str(TEST_DATA_DIR)
os.environ["CYCLE_MEAL_PLANNER_ENV"] = "test"
