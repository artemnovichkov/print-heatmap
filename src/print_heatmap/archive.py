"""The print archive: a small JSON file that outlives the cloud's ~3-month history.

Only what the charts need is kept. The raw API task also carries the printer's
serial number, cover image links and slicer settings, which stay out.
"""

from __future__ import annotations

import json
import os
from datetime import datetime

SCHEMA = 1


def parse_time(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def slim(task, titles=True):
    """Archive record for one raw API task, or None while it is still printing."""
    start, end = task.get("startTime"), task.get("endTime")
    if not start or not end or (parse_time(end) - parse_time(start)).total_seconds() < 60:
        return None
    record = {
        "id": task["id"],
        "start": start,
        "end": end,
        "status": "finished" if task.get("status") == 2 else "failed",
        "grams": round(float(task.get("weight") or 0), 2),
        "filaments": [
            {
                "color": "#" + (slot.get("sourceColor") or slot.get("targetColor"))[:6].upper(),
                "type": slot.get("filamentType") or "",
                "grams": round(float(slot.get("weight") or 0), 2),
            }
            for slot in task.get("amsDetailMapping") or []
            if slot.get("sourceColor") or slot.get("targetColor")
        ],
    }
    if task.get("deviceModel"):
        record["printer"] = task["deviceModel"]
    if titles and task.get("title"):
        record["title"] = task["title"]
    return record


def load(path):
    try:
        with open(path) as f:
            data = json.load(f)
    except FileNotFoundError:
        return []
    if "hits" in data:  # a raw my/tasks response saved earlier
        return [r for r in map(slim, data["hits"]) if r]
    return data.get("prints", [])


def merge(old, new, titles=True):
    records = {r["id"]: r for r in old}
    records.update((r["id"], r) for r in new)
    merged = sorted(records.values(), key=lambda r: r["start"], reverse=True)
    if not titles:
        merged = [{k: v for k, v in r.items() if k != "title"} for r in merged]
    return merged


def save(path, records):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    # No timestamp: an unchanged archive stays byte-identical, so the action commits nothing.
    data = {"schema": SCHEMA, "prints": records}
    with open(path, "w") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")
