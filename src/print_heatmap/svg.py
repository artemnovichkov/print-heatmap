"""GitHub-style contribution grid as an SVG."""

from __future__ import annotations

from datetime import timedelta

from .stats import Day, level, quartiles, streaks, year_start
from .text import color_name

CELL, GAP = 11, 3
STEP = CELL + GAP
LEFT, TOP = 42, 40
WIDTH = LEFT + 53 * STEP + 10
STRIP = 5  # height of the weekly filament strip
DOT = [0, 5, 7, 9, 11]  # filament-mode dot size per level
# Activity ramps: empty cell + 4 levels, one hue, lightness monotonic (darker = more on light,
# brighter = more on dark), adjacent steps >= 11 ΔE in OKLab. Orange is the default so the
# chart doesn't pass for a GitHub contribution graph; green is GitHub's own.
PALETTES = {
    "orange": {
        "light": ["#ebedf0", "#fdba74", "#f97316", "#c2410c", "#7c2d12"],
        "dark": ["#161b22", "#7c2d12", "#c2410c", "#f97316", "#fdba74"],
    },
    "blue": {
        "light": ["#ebedf0", "#93c5fd", "#3b82f6", "#1d4ed8", "#1e3a8a"],
        "dark": ["#161b22", "#1e3a8a", "#1d4ed8", "#3b82f6", "#93c5fd"],
    },
    "purple": {
        "light": ["#ebedf0", "#c4b5fd", "#8b5cf6", "#6d28d9", "#4c1d95"],
        "dark": ["#161b22", "#4c1d95", "#6d28d9", "#8b5cf6", "#c4b5fd"],
    },
    "green": {
        "light": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
        "dark": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"],
    },
}
CHROME = {
    "light": ".bg{fill:#fff}text{fill:#57606a}.t{fill:#24292f}rect.c{stroke:#1b1f2312}rect.f{stroke:#1b1f2326}"
    "rect.f.hi{stroke:#1b1f2399}",
    "dark": ".bg{fill:#0d1117}text{fill:#8b949e}.t{fill:#e6edf3}rect.c{stroke:#ffffff0d}rect.f{stroke:#ffffff1a}"
    "rect.f.lo{stroke:#ffffffa0}",
}
UNITS = {"hours": "h", "grams": "g", "prints": "prints"}


def style(theme, palette):
    def rules(mode):
        return CHROME[mode] + "".join(f".l{i}{{fill:{c}}}" for i, c in enumerate(PALETTES[palette][mode]))

    base = ".t{font-size:13px;font-weight:600}rect.c,rect.f{stroke-width:1}"
    if theme == "auto":
        return base + rules("light") + "@media (prefers-color-scheme: dark){" + rules("dark") + "}"
    return base + rules(theme)


def fmt(v, metric):
    if metric == "prints":
        return f"{v:g} print{'s' if v != 1 else ''}"
    if metric == "grams":
        return f"{v:.0f} g"
    return f"{v:.1f} h"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def luminance(hex_color):
    r, g, b = (int(hex_color.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_class(fill):
    """Near-white filament gets a darker outline on light backgrounds, near-black a lighter one on dark."""
    lum = luminance(fill)
    return "f hi" if lum > 0.75 else "f lo" if lum < 0.08 else "f"


def dot(x, y, lv, fill, tip=""):
    """A filament-mode cell: the colour is the filament, the size is the activity level."""
    size = DOT[lv]
    inset = (CELL - size) / 2
    title = f"<title>{esc(tip)}</title>" if tip else ""
    return (
        f'<rect class="{contrast_class(fill)}" x="{x + inset:g}" y="{y + inset:g}" width="{size}" '
        f'height="{size}" rx="{1 + lv * 0.25:g}" fill="{fill}">{title}</rect>'
    )


def week_colors(days, first, end):
    """Most used filament colour of each grid week, or None."""
    out = []
    for week in range(53):
        grams = {}
        for i in range(7):
            d = first + timedelta(weeks=week, days=i)
            if d <= end and d in days:
                for color, g in days[d].filament.items():
                    grams[color] = grams.get(color, 0) + g
        out.append(max(grams, key=grams.get) if grams else None)
    return out


def top_filaments(days, first, end, n=3):
    """[(colour, share)] of the most used filament colours in the grid."""
    grams = {}
    for d, day in days.items():
        if first <= d <= end:
            for color, g in day.filament.items():
                grams[color] = grams.get(color, 0) + g
    total = sum(grams.values()) or 1
    return [(c, g / total) for c, g in sorted(grams.items(), key=lambda x: -x[1])[:n]]


def render(days, end, metric="hours", colors="activity", theme="auto", strip=False, palette="orange"):
    first = year_start(end)
    span = [d for d in days if first <= d <= end]
    th = quartiles(days[d].value(metric) for d in span)
    grid_bottom = TOP + 7 * STEP - GAP
    strip_y = grid_bottom + 6
    ly = (strip_y + STRIP if strip else grid_bottom) + 12
    height = ly + CELL + 12

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" '
        'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" font-size="10">',
        f"<style>{style(theme, palette)}</style>",
        f'<rect class="bg" width="{WIDTH}" height="{height}" rx="6"/>',
    ]

    total = sum(days[d].value(metric) for d in span)
    prints = sum(days[d].prints for d in span)
    failed = sum(days[d].failed for d in span)
    longest, current = streaks(days, first, end)
    if metric == "prints":
        summary = f"{prints} prints in the last year"
    else:
        summary = f"{fmt(total, metric)} of printing in the last year · {prints} prints"
    if failed:
        summary += f" · {failed} failed"
    summary += f" · longest streak {longest} d"
    out.append(f'<text class="t" x="{LEFT}" y="20">{esc(summary)}</text>')

    for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        out.append(f'<text x="8" y="{TOP + row * STEP + 9}">{name}</text>')

    last_month, last_label = None, -9
    for week in range(53):
        col_start = first + timedelta(weeks=week)
        if col_start.month != last_month and week < 52:
            # label the first column of each month, but not closer than 3 columns to the last label
            if (col_start.day <= 7 or week == 0) and week - last_label >= 3:
                out.append(f'<text x="{LEFT + week * STEP}" y="{TOP - 6}">{col_start:%b}</text>')
                last_label = week
            last_month = col_start.month
        for row in range(7):
            d = col_start + timedelta(days=row)
            if d > end:
                break
            x, y = LEFT + week * STEP, TOP + row * STEP
            day = days.get(d, Day())
            lv = level(day.value(metric), th)
            tip = f"{fmt(day.value(metric), metric)} on {d:%b} {d.day}, {d.year}"
            if day.prints:
                tip += f" · {', '.join(dict.fromkeys(day.titles))}"
            if day.failed:
                tip += f" · {day.failed} failed"
            if colors == "filament" and lv and day.filament:
                top_color = max(day.filament, key=day.filament.get)
                out.append(f'<rect class="c l0" x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2"/>')
                out.append(dot(x, y, lv, top_color, tip))
            else:
                out.append(
                    f'<rect class="c l{lv}" x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2">'
                    f"<title>{esc(tip)}</title></rect>"
                )

    if strip:
        for week, color in enumerate(week_colors(days, first, end)):
            x = LEFT + week * STEP
            cls = contrast_class(color) if color else "c l0"
            fill = f' fill="{color}"' if color else ""
            out.append(f'<rect class="{cls}" x="{x}" y="{strip_y}" width="{CELL}" height="{STRIP}" rx="1.5"{fill}/>')

    lx = WIDTH - 10 - 5 * STEP - 60
    out.append(f'<text x="{lx - 28}" y="{ly + 9}">Less</text>')
    for i in range(5):
        if colors == "filament" and i:
            out.append(dot(lx + i * STEP, ly, i, "#8b949e"))
        else:
            out.append(f'<rect class="c l{i}" x="{lx + i * STEP}" y="{ly}" width="{CELL}" height="{CELL}" rx="2"/>')
    out.append(f'<text x="{lx + 5 * STEP + 4}" y="{ly + 9}">More</text>')
    if strip:
        # name the top filaments of the strip; ~5.6 px per character at 10 px
        x = LEFT
        for color, share in top_filaments(days, first, end):
            label = esc(f"{color_name(color)} {share:.0%}")
            out.append(f'<rect class="{contrast_class(color)}" x="{x}" y="{ly + 1}" width="9" height="9" rx="2" fill="{color}"/>')
            out.append(f'<text x="{x + 13}" y="{ly + 9}">{label}</text>')
            x += 13 + round(5.6 * len(label)) + 12
        out.append(f'<text x="{x + 4}" y="{ly + 9}">· Current streak {current} d</text>')
    else:
        out.append(f'<text x="{LEFT}" y="{ly + 9}">Current streak {current} d · metric: {UNITS[metric]}</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"
