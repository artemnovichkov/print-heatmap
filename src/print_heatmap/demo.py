"""A year of plausible hobby printing, for trying the tool without an account."""

from __future__ import annotations

import random
from datetime import datetime, time, timedelta, timezone

PALETTE = ["#FFFFFF", "#000000", "#00AE42", "#FF6A13", "#0A2989", "#F4EE2A", "#C12E1F", "#8E9089"]
TITLES = ["Desk calendar", "Shadow pumpkin", "Keychain", "Planter", "Calibration cube", "Cable clip", "Spool holder"]


def records(end, seed=7):
    rng = random.Random(seed)
    bursts = [end - timedelta(days=d) for d in (12, 40, 95, 160, 230, 300)]
    out, task_id = [], 1
    for offset in range(371):
        day = end - timedelta(days=offset)
        p = 0.22 + (0.25 if day.weekday() >= 5 else 0)
        p += sum(0.5 for b in bursts if 0 <= (b - day).days < 9)
        if rng.random() > min(p, 0.95):
            continue
        clock = datetime.combine(day, time(), timezone.utc) + timedelta(hours=rng.uniform(7, 18))
        for _ in range(rng.choice([1, 1, 1, 2, 2, 3])):
            hours = rng.choice([0.4, 0.8, 1.5, 2.5, 4, 7, 12]) * rng.uniform(0.8, 1.2)
            colors = rng.sample(PALETTE, rng.choice([1, 1, 2, 3]))
            grams = hours * rng.uniform(9, 16)
            failed = rng.random() < 0.07
            spent = hours * (rng.uniform(0.1, 0.6) if failed else 1)
            out.append({
                "id": task_id,
                "start": clock.isoformat(),
                "end": (clock + timedelta(hours=spent)).isoformat(),
                "status": "failed" if failed else "finished",
                "grams": round(grams, 2),
                "filaments": [{"color": c, "type": "PLA", "grams": round(grams / len(colors), 2)} for c in colors],
                "printer": "P2S",
                "title": rng.choice(TITLES),
            })
            task_id += 1
            clock += timedelta(hours=spent + 0.2)
    return out
