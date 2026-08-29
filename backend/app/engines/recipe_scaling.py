from decimal import Decimal, ROUND_CEILING

VALID_SCALING_MODES = {"LINEAR", "FIXED", "ROUND_UP", "MANUAL"}


class RecipeScalingError(ValueError):
    pass


def scale_quantity(quantity: Decimal, scale_factor: Decimal, scaling_mode: str) -> tuple[Decimal, bool]:
    mode = scaling_mode.upper()
    if mode not in VALID_SCALING_MODES:
        raise RecipeScalingError(f"Unsupported scaling mode: {scaling_mode}")
    if quantity < 0 or scale_factor <= 0:
        raise RecipeScalingError("Quantity must be nonnegative and scale factor must be positive")

    if mode == "LINEAR":
        return quantity * scale_factor, False
    if mode == "ROUND_UP":
        return (quantity * scale_factor).quantize(Decimal("1"), rounding=ROUND_CEILING), False
    if mode == "FIXED":
        return quantity, False
    return quantity, True
