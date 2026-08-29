from decimal import Decimal

from app.models.reference import MeasurementUnit


class UnitConversionError(ValueError):
    pass


def convert_quantity(quantity: Decimal, from_unit: MeasurementUnit, to_unit: MeasurementUnit) -> Decimal:
    if from_unit.unit_family != to_unit.unit_family:
        raise UnitConversionError(
            f"Cannot safely convert {from_unit.unit_family} to {to_unit.unit_family}"
        )

    base_quantity = quantity * Decimal(from_unit.base_multiplier)
    return base_quantity / Decimal(to_unit.base_multiplier)
