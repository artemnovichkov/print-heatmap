"""Plain-text heatmap for a pinned gist.

A pinned gist shows only the first 5 lines, so the default `months` layout is a
summary, a blank line and the last 3 months as a row each, a character per day.
The `grid` layout mirrors the SVG instead: a column per week, a row per weekday,
two block characters plus a space per cell so cells come out roughly square
with even gaps; it needs 9 lines, so a pinned card cuts it off.
Both shade days by the same quartile levels as the SVG.
"""

from __future__ import annotations

from datetime import timedelta

from .stats import level, quartiles, streaks, year_start

WEEKS = 13  # ~3 months fits a pinned gist's width
MONTHS = 3
SHADES = ["··", "░░", "▒▒", "▓▓", "██"]
DAY_SHADES = ["·", "░", "▒", "▓", "█"]
LAYOUTS = ("months", "grid")
ROW_LABELS = ["   ", "Mon", "   ", "Wed", "   ", "Fri", "   "]
TITLE = "🖨️ 3D printing activity"
WIDTH = 46

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


def total(v, metric):
    if metric == "grams":
        return mass(v)
    if metric == "prints":
        return f"{v:.0f} pr"
    return f"{v:.0f} h"


def render(days, end, metric="hours", layout="months"):
    first = year_start(end)
    span = [d for d in days if first <= d <= end]
    hours = sum(days[d].hours for d in span)
    grams = sum(days[d].grams for d in span)
    prints = sum(days[d].prints for d in span)
    longest, _ = streaks(days, first, end)
    # thresholds from the whole year, so a day has the same level as in the SVG
    th = quartiles(days[d].value(metric) for d in span)
    summary = f"{prints} prints · {hours:.0f} h · {mass(grams)} · streak {longest} d"
    if layout == "grid":
        return grid(days, end, metric, th, summary)
    return months(days, end, metric, th, summary)


def months(days, end, metric, th, summary):
    starts = [end.replace(day=1)]
    for _ in range(MONTHS - 1):
        starts.insert(0, (starts[0] - timedelta(days=1)).replace(day=1))
    lines = [summary, ""]  # blank line between the totals and the months
    for m in starts:
        cells, value = "", 0.0
        d = m
        while d.month == m.month and d <= end:
            day = days.get(d)
            cells += DAY_SHADES[level(day.value(metric), th) if day else 0]
            value += day.value(metric) if day else 0
            d += timedelta(days=1)
        lines.append(f"{m:%b} {cells:<31} {total(value, metric):>6}")
    return "\n".join(lines) + "\n"


def grid(days, end, metric, th, summary, weeks=WEEKS):
    start = end - timedelta(days=(end.weekday() + 1) % 7) - timedelta(weeks=weeks - 1)
    header = [" "] * (4 + weeks * 3)
    for w in range(weeks):
        d = start + timedelta(weeks=w)
        if d.day <= 7:  # the column holding the 1st of a month
            header[4 + w * 3:7 + w * 3] = f"{d:%b}"

    lines = [summary, "".join(header).rstrip()]
    for row, label in enumerate(ROW_LABELS):
        cells = []
        for w in range(weeks):
            d = start + timedelta(weeks=w, days=row)
            if d > end:
                break
            cells.append(SHADES[level(days[d].value(metric), th) if d in days else 0])
        lines.append(f"{label} {' '.join(cells)}".rstrip())
    return "\n".join(lines) + "\n"
