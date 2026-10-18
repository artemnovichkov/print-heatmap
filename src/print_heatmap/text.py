"""Plain-text summary for a pinned gist: a pinned gist shows only its first few lines."""

from __future__ import annotations

from datetime import timedelta

from .stats import filament_totals, streaks, year_start

WIDTH = 46
SPARK = "▁▂▃▄▅▆▇█"
WEEKS = 26
TITLE = "🖨️ 3D printing in the last year"

# Common Bambu Lab filament colours, for naming a hex colour in plain text.
COLOR_NAMES = {
    "Black": "000000", "White": "FFFFFF", "Gray": "8E9089", "Silver": "A6A9AA",
    "Red": "C12E1F", "Orange": "FF6A13", "Yellow": "F4EE2A", "Green": "00AE42",
    "Mint": "A6DDC6", "Blue": "0A2989", "Cyan": "0086D6", "Purple": "5E43B7",
    "Pink": "F55A74", "Magenta": "EC008C", "Brown": "9D432C", "Beige": "D3C5A3",
}


def color_name(hex_color):
    rgb = [int(hex_color.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]

    def distance(ref):
        return sum((a - int(ref[i * 2:i * 2 + 2], 16)) ** 2 for i, a in enumerate(rgb))

    return min(COLOR_NAMES, key=lambda name: distance(COLOR_NAMES[name]))


def mass(grams):
    return f"{grams / 1000:.1f} kg" if grams >= 1000 else f"{grams:.0f} g"


def sparkline(values):
    top = max(values) or 1
    return "".join("·" if v <= 0 else SPARK[min(len(SPARK) - 1, int(v / top * len(SPARK)))] for v in values)


def render(days, records, end, tz):
    first = year_start(end)
    span = [d for d in days if first <= d <= end]
    hours = sum(days[d].hours for d in span)
    grams = sum(days[d].grams for d in span)
    prints = sum(days[d].prints for d in span)
    longest, _ = streaks(days, first, end)

    lines = [f"{prints} prints · {hours:.0f} h · {mass(grams)} · streak {longest} d"]

    week_end = end
    weekly = []
    for _ in range(WEEKS):
        week = [week_end - timedelta(days=i) for i in range(7)]
        weekly.append(sum(days[d].hours for d in week if d in days))
        week_end -= timedelta(days=7)
    weekly.reverse()
    lines.append(f"Weekly ▕{sparkline(weekly)}▏ peak {max(weekly):.0f} h")

    filaments = filament_totals(records, first, end, tz)
    used = sum(g for _, _, g in filaments) or 1
    most = filaments[0][2] if filaments else 1
    for color, kind, g in filaments[:3]:
        name = f"{color_name(color)} {kind}".strip()[:15]
        filled = max(1, round(g / most * 14))  # bars relative to the most used filament
        lines.append(f"{name:<15} {'█' * filled}{'░' * (14 - filled)} {mass(g):>7} {g / used:4.0%}")
    if not filaments:
        lines.append("No filament data yet")
    return "\n".join(lines) + "\n"
