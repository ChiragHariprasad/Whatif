"""Build reproducible synthetic demo records without placing hidden truths in the product model.

Run: python data/synthetic/generate.py
It writes `synthetic_year.json` for the time-machine story and a separate
`ground_truth.json` for an optional demo reveal.
"""
from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent
RNG = random.Random(42017)

PARTNERS = [
    ("rajan-jars", "Rajan Jars", 10), ("aarav-waxworks", "Aarav Waxworks", 7),
    ("packwell", "PackWell Packaging", 5), ("inklane", "InkLane Printers", 4),
    ("speedy-courier", "Speedy Courier", 7),
]
LEVERS = [("price", "premium", .10), ("price", "core", .08), ("ads", "core", .20), ("promotion", "core", .10), ("restock", "premium", 260)]


def build() -> tuple[dict, dict]:
    start = date(2025, 7, 7); decisions = []
    for index in range(30):
        lever, group, change = LEVERS[index % len(LEVERS)]; week = 3 + index * 1
        # Synthetic result has deliberate, undisclosed patterns: premium is less elastic,
        # core ads saturate, and promotions pull sales forward.
        if lever == "price": base = 32000 if group == "premium" else 12000
        elif lever == "ads": base = 17000 - index * 260
        elif lever == "promotion": base = 11000
        else: base = 7000
        actual = round(base + RNG.gauss(0, abs(base) * .35), -2)
        decisions.append({"id": f"S-{index+1:03d}", "week": week, "date": (start + timedelta(weeks=week)).isoformat(), "lever": lever, "group": group, "change": change, "actual_effect": actual, "confounded": index in {5, 14, 22}})
    promises = []
    hedge_words = ("should be", "hopefully", "expect", "")
    for index in range(60):
        key, name, promised = PARTNERS[index % len(PARTNERS)]; hedge = hedge_words[index % len(hedge_words)]
        ratio = 1.6 if key == "rajan-jars" else 1.2 if key == "speedy-courier" else 1.05
        actual = max(1, round(promised * ratio + (3 if hedge else 0) + RNG.gauss(0, 1.4), 1))
        promises.append({"id": f"SP-{index+1:03d}", "week": index % 52, "partner": key, "quote": f"{name}: the order {hedge} ready in {promised} days.", "promised_days": promised, "actual_days": actual, "hedged": bool(hedge)})
    truth = {"note": "Synthetic demo ground truth. Do not feed it to the learner.", "premium_elasticity": -.55, "core_elasticity": -2.15, "ad_half_saturation": 1.25, "rajan_jars_ratio": 1.6, "hedge_extra_days": 3.0}
    return {"seed": 42017, "business": "Lumen & Wick Candle Co.", "decisions": decisions, "promises": promises}, truth


if __name__ == "__main__":
    events, truth = build(); (ROOT / "synthetic_year.json").write_text(json.dumps(events, indent=2), encoding="utf-8"); (ROOT / "ground_truth.json").write_text(json.dumps(truth, indent=2), encoding="utf-8"); print("Wrote 30 decisions and 60 promises.")
