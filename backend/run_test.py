from __future__ import annotations

import os
from pathlib import Path

from testdata.seed_test_db import TEST_DB, seed


def main() -> None:
    seed(reset=False)
    os.environ["CYCLE_MEAL_PLANNER_DATABASE_URL"] = f"sqlite:///{Path(TEST_DB).as_posix()}"
    os.environ["CYCLE_MEAL_PLANNER_ENV"] = "testdata"

    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
