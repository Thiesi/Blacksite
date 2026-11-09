"""Compact numeric text for caller views and logs."""


def display_number(value: int | float) -> str:
    """Keep whole numbers short and fractional readouts to two decimals."""
    return f"{value:.2f}".rstrip("0").rstrip(".")
