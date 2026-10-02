"""Unit handling. Everything is converted to a base unit per dimension:
mass -> grams, volume -> millilitres, count -> pieces. Decimal throughout."""

from decimal import Decimal

# unit -> (dimension, factor to the base unit)
UNITS: dict[str, tuple[str, Decimal]] = {
    "g": ("mass", Decimal("1")),
    "kg": ("mass", Decimal("1000")),
    "oz": ("mass", Decimal("28.349523125")),
    "lb": ("mass", Decimal("453.59237")),
    "ml": ("volume", Decimal("1")),
    "l": ("volume", Decimal("1000")),
    "count": ("count", Decimal("1")),
    "dozen": ("count", Decimal("12")),
}

BASE_UNIT = {"mass": "g", "volume": "ml", "count": "count"}


def dimension(unit: str) -> str | None:
    entry = UNITS.get(unit)
    return entry[0] if entry else None


def to_base(quantity: Decimal, unit: str) -> tuple[str, Decimal]:
    """Return (dimension, quantity in base unit). Raises KeyError on unknown unit."""
    dim, factor = UNITS[unit]
    return dim, quantity * factor
