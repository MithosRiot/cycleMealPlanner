from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, event, update
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.completion import MealCompletion
from app.models.reservation import InventoryReservation


class ProductionCoverageReservation(Base):
    __tablename__ = "production_coverage_reservations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("meal_cycles.id", ondelete="CASCADE"), nullable=False)
    planned_meal_id: Mapped[int] = mapped_column(Integer, nullable=False)
    cycle_slot_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_origin_planned_meal_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_record_id: Mapped[int | None] = mapped_column(Integer)
    source_recipe_output_id: Mapped[int | None] = mapped_column(Integer)
    lot_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_lots.id", ondelete="RESTRICT"))
    requested_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    reserved_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False, default=Decimal("0"))
    shortage_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False, default=Decimal("0"))
    unit_id: Mapped[int] = mapped_column(ForeignKey("measurement_units.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    release_reason: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    released_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        CheckConstraint("source_type IN ('LEFTOVER','RECIPE_OUTPUT')", name="ck_production_coverage_source_type"),
        CheckConstraint("requested_quantity > 0", name="ck_production_coverage_requested_positive"),
        CheckConstraint("reserved_quantity >= 0", name="ck_production_coverage_reserved_nonnegative"),
        CheckConstraint("shortage_quantity >= 0", name="ck_production_coverage_shortage_nonnegative"),
        CheckConstraint("status IN ('ACTIVE','RELEASED')", name="ck_production_coverage_status"),
    )


@event.listens_for(MealCompletion, "after_update")
def _release_source_reservations_after_finalize(_mapper, connection, target: MealCompletion) -> None:
    if target.status != "FINALIZED":
        return
    connection.execute(
        update(InventoryReservation)
        .where(
            InventoryReservation.planned_meal_id == target.planned_meal_id,
            InventoryReservation.status == "ACTIVE",
        )
        .values(status="RELEASED")
    )
