"""Currency conversion and presentation helpers."""

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def money(value: Decimal | int | str | float | None) -> Decimal:
    """Convert a numeric input to a two-decimal Decimal using string conversion."""
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def format_currency(value: Decimal | int | float | None, currency_code: str = "CAD") -> str:
    """Format a value with the configured ISO currency code."""
    return f"{currency_code} ${money(value):,.2f}"
