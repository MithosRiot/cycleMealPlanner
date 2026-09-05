from datetime import date
from decimal import Decimal
from pydantic import BaseModel


class UseSoonRecommendationRead(BaseModel):
    lot_id: int
    source_type: str
    source_id: int | None
    source_name: str
    ingredient_id: int | None
    location_id: int
    location_name: str
    available_quantity: Decimal
    unit_id: int
    unit_code: str
    expiration_date: date
    days_remaining: int


class UseSoonResponse(BaseModel):
    horizon_days: int
    recommendations: list[UseSoonRecommendationRead]
