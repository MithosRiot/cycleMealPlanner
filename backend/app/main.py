from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from sqlalchemy import text

from app.api.allocation import router as allocation_router
from app.api.combined_prep import router as combined_prep_router
from app.api.completion import router as completion_router
from app.api.cooking import router as cooking_router
from app.api.cycle_validation import router as cycle_validation_router
from app.api.equipment import router as equipment_router
from app.api.expiration_planning import router as expiration_planning_router
from app.api.gather import router as gather_router
from app.api.gather_locations import router as gather_locations_router
from app.api.ingredients import router as ingredients_router
from app.api.inventory import router as inventory_router
from app.api.meal_cycles import router as meal_cycles_router
from app.api.meals import router as meals_router
from app.api.planned_meals import router as planned_meals_router
from app.api.prep_schedule import router as prep_schedule_router
from app.api.recipes import router as recipes_router
from app.api.recipe_outputs import router as recipe_outputs_router
from app.api.recipe_variants import router as recipe_variants_router
from app.api.reference import router as reference_router
from app.api.reservations import router as reservations_router
from app.api.shopping import router as shopping_router
from app.config import get_settings
from app.database.migrations import run_migrations
from app.database.session import engine
from app.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    logger.info("application_started")
    yield
    engine.dispose()
    logger.info("application_stopped")


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(reference_router)
app.include_router(ingredients_router)
app.include_router(equipment_router)
app.include_router(recipes_router)
app.include_router(recipe_outputs_router)
app.include_router(recipe_variants_router)
app.include_router(cooking_router)
app.include_router(completion_router)
app.include_router(inventory_router)
app.include_router(reservations_router)
app.include_router(allocation_router)
app.include_router(gather_router)
app.include_router(gather_locations_router)
app.include_router(meals_router)
app.include_router(meal_cycles_router)
app.include_router(planned_meals_router)
app.include_router(prep_schedule_router)
app.include_router(combined_prep_router)
app.include_router(expiration_planning_router)
app.include_router(cycle_validation_router)
app.include_router(shopping_router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok"}
