"""How numbers, ranges and warnings are written, everywhere in the app.

One place, so the cards, the Plants page, the warnings and Sprout's plant
table all read the same: ranges use an en dash ("18–27 °C", "50–70% RH",
"pH 6.0–6.5") and readings have one decimal ("24.3 °C", "61.0% RH").
No Tk here.
"""
DASH = "–"        # en dash, for ranges (and for a missing value)
ELLIPSIS = "…"


def _whole_or_tenth(value):
    """18 -> "18", 18.5 -> "18.5": range ends are usually whole numbers."""
    value = float(value)
    return f"{value:.0f}" if value.is_integer() else f"{value:.1f}"


def _span(low, high, write):
    if low is None or high is None:
        return None
    return f"{write(low)}{DASH}{write(high)}"


def reading(value):
    """A reading without its unit, for the big numbers: "24.3"."""
    return f"{value:.1f}"


def temperature(value):
    return f"{reading(value)} °C"


def humidity(value):
    return f"{reading(value)}% RH"


def temperature_range(low, high):
    span = _span(low, high, _whole_or_tenth)
    return f"{span} °C" if span else DASH


def humidity_range(low, high):
    span = _span(low, high, _whole_or_tenth)
    return f"{span}% RH" if span else DASH


def ph_range(low, high):
    span = _span(low, high, lambda value: f"{float(value):.1f}")
    return f"pH {span}" if span else DASH


def ideal_ranges(plant):
    """ "18–27 °C, 50–70% RH" for a plant dict from plant_db."""
    return (f"{temperature_range(plant['min_temp'], plant['max_temp'])}, "
            f"{humidity_range(plant['min_hum'], plant['max_hum'])}")
