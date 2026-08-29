from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    app_name: str
    environment: str
    database_url: str
    log_level: str


def get_settings() -> Settings:
    data_dir = Path(os.getenv("CYCLE_MEAL_PLANNER_DATA_DIR", "./data")).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    database_url = os.getenv(
        "CYCLE_MEAL_PLANNER_DATABASE_URL",
        f"sqlite:///{data_dir / 'mealplanner.db'}",
    )
    return Settings(
        app_name="Cycle Meal Planner",
        environment=os.getenv("CYCLE_MEAL_PLANNER_ENV", "development"),
        database_url=database_url,
        log_level=os.getenv("CYCLE_MEAL_PLANNER_LOG_LEVEL", "INFO").upper(),
    )
