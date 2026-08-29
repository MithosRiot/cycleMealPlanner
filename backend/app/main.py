from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from sqlalchemy import text

from app.api.ingredients import router as ingredients_router
from app.api.inventory import router as inventory_router
from app.api.recipes import router as recipes_router
from app.api.reference import router as reference_router
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
app.include_router(recipes_router)
app.include_router(inventory_router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok"}
