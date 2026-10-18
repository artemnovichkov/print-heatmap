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


def quartiles(values):
    """Level thresholds: quartiles of the non-zero values, like GitHub's contribution graph."""
    vals = sorted(v for v in values if v > 0)
    if not vals:
        return [1, 2, 3]
    return [vals[int(len(vals) * q)] for q in (0.25, 0.5, 0.75)]


def level(v, thresholds):
    """0 for nothing, 1-4 by quartile."""
    if v <= 0:
        return 0
    return 1 + sum(v > t for t in thresholds)


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

