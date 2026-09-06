from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class PlannedMealRevision(Base):
    __tablename__ = "planned_meal_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cycle_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    cycle_slot_id: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_meal_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    snapshot_name: Mapped[str] = mapped_column(String(160), nullable=False)
    snapshot_description: Mapped[str | None] = mapped_column(Text)
    planned_servings: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    planned_leftover_servings: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    component_serving_overrides: Mapped[str] = mapped_column(Text, nullable=False)
    scaled_components: Mapped[str] = mapped_column(Text, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
