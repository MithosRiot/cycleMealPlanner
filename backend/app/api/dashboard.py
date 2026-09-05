from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.dashboard import UseSoonRecommendationRead, UseSoonResponse
from app.services.dashboard_use_soon import use_soon_rows

router = APIRouter(tags=["dashboard"])


@router.get("/api/dashboard/use-soon", response_model=UseSoonResponse)
def get_use_soon(
    days: int = Query(default=7, ge=1, le=30),
    db: Session = Depends(get_db),
) -> UseSoonResponse:
    return UseSoonResponse(
        horizon_days=days,
        recommendations=[UseSoonRecommendationRead(**row) for row in use_soon_rows(db, horizon_days=days)],
    )
