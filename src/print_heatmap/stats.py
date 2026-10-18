"""Per-day totals from archive records."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta

from .archive import parse_time

METRICS = ("hours", "grams", "prints")


@dataclass
class Day:
    hours: float = 0.0
    grams: float = 0.0
    prints: int = 0
    failed: int = 0
    titles: list = field(default_factory=list)
    filament: dict = field(default_factory=lambda: defaultdict(float))  # hex colour -> grams

    def value(self, metric):
        return getattr(self, metric)


def aggregate(records, tz):
    """Days keyed by local date. Failed prints are counted, but add no hours or grams."""
    days = defaultdict(Day)
    for r in records:
        start, end = parse_time(r["start"]), parse_time(r["end"])
        d = days[start.astimezone(tz).date()]
        if r["status"] != "finished":
            d.failed += 1
            continue
        d.prints += 1
        d.hours += (end - start).total_seconds() / 3600
        d.grams += r["grams"]
        d.titles.append(r.get("title") or "untitled")
        for f in r["filaments"]:
            d.filament[f["color"]] += f["grams"]
    return days


def year_start(end):
    """First day of the 53-week grid that ends with `end`; weeks start on Sunday like GitHub."""
    return end - timedelta(days=(end.weekday() + 1) % 7) - timedelta(weeks=52)


def streaks(days, start, end):
    """(longest, current) runs of days with prints. Like GitHub, an empty today doesn't break the current one."""
    longest = run = before_today = 0
    d = start
    while d <= end:
        before_today = run
        run = run + 1 if d in days and days[d].prints else 0
        longest = max(longest, run)
        d += timedelta(days=1)
    return longest, run or before_today


def filament_totals(records, start, end, tz):
    """[(colour, type, grams)] for finished prints between the dates, most used first."""
    totals = defaultdict(float)
    for r in records:
        if r["status"] == "finished" and start <= parse_time(r["start"]).astimezone(tz).date() <= end:
            for f in r["filaments"]:
                totals[(f["color"], f["type"])] += f["grams"]
    return sorted(((c, t, g) for (c, t), g in totals.items()), key=lambda x: -x[2])
