"""Seed all three synthetic worlds into SQLite and Hindsight Cloud.

Worlds:
1. Ember & Wick Candle Co. (D2C hero) -> whatif.db & whatif-ember-wick bank
2. Northlight Studio (Agency) -> whatif-northlight-studio.db & whatif-northlight-studio bank
3. Brew Lane Café (Single-outlet café) -> whatif-brew-lane-cafe.db & whatif-brew-lane-cafe bank

Follows all integrity rules:
- No hand-edited outputs, ranges, or scores.
- Real outputs generated through simulate(), commit(), review(), add_promise(), deliver_promise().
- Learner sees only observed actuals and owner tags; never ground truth.
- 5 deliberate memory features in every world: distractors, conflicting precedent, belief change, noisy review, cold-start partner.
- Banks saved runs library (18 runs) and 10-seed rehearsal for the hard Diwali scenario.
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import random
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv(override=True)

from apps.api.whatif.beliefs import initial_beliefs, update_partner
from apps.api.whatif.config import (
    ember_wick_business,
    northlight_studio_business,
    brew_lane_cafe_business,
    Business,
)
from apps.api.whatif.learning import decision_memory_text, review
from apps.api.whatif.memory import HindsightMemory
from apps.api.whatif.simulator import Decision, parse_question, simulate, title_for
from apps.api.whatif.storage import Store, utcnow

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT
START_DATE = date(2025, 7, 7)

# --- Ground Truth Definitions (Kept strictly outside the learner) ---

TRUTHS = {
    "ember-wick": {
        "world_id": "ember-wick",
        "business": "Ember & Wick Candle Co.",
        "note": "Synthetic demo ground truth. Never fed to the learner.",
        "premium_elasticity": -0.52,
        "core_elasticity": -1.74,
        "ad_saturation_budget": 400000.0,
        "rajan_jars_ratio": 1.60,
        "hedge_extra_days": 3.0,
        "speedy_courier_ratio": 1.71,
        "festival_lift_factor": 1.45,
    },
    "northlight-studio": {
        "world_id": "northlight-studio",
        "business": "Northlight Studio",
        "note": "Synthetic demo ground truth. Never fed to the learner.",
        "retainer_elasticity": -0.42,
        "project_elasticity": -1.32,
        "new_hire_ramp_weeks": 6,
        "apex_digital_payment_days": 47.0,
        "scaleco_payment_days": 62.0,
        "devcraft_contractor_ratio": 2.0,
        "contractor_hedge_extra_days": 4.0,
        "fixed_price_overrun_pct": 0.20,
    },
    "brew-lane-cafe": {
        "world_id": "brew-lane-cafe",
        "business": "Brew Lane Café",
        "note": "Synthetic demo ground truth. Never fed to the learner.",
        "weekend_dinein_elasticity": -0.58,
        "weekday_dinner_elasticity": -1.14,
        "late_night_revenue_gain_pct": 0.03,
        "late_night_labor_cost_pct": 0.18,
        "promo_pullforward_lift": 0.35,
        "promo_pullforward_drain": -0.18,
        "freshfarms_produce_delay_days": 0.8,
        "delivery_app_payout_days": 16.0,
    },
}

# Distractor notes (15 per world) to verify precision
DISTRACTORS = {
    "ember-wick": [
        "Staff birthday: Ananya brought saffron cupcakes to the pouring studio today.",
        "Label printer jammed again on line 2; replacement thermal printhead ordered.",
        "Photographer session booked for new monsoon catalog visuals on Thursday.",
        "Warehouse AC filter replaced during scheduled maintenance check.",
        "Sample fragrances received from Grasse supplier: Amber Noir, Cardamom Chai.",
        "Cardboard carton shipment arrived with minor water damage on 2 outer boxes.",
        "Studio Wi-Fi router upgraded to Wi-Fi 6 after morning connectivity glitch.",
        "Local artisan fair booth application submitted for upcoming winter fest.",
        "Office cleaning crew switched to Monday evening schedule.",
        "New safety goggles and heat-resistant gloves distributed to pouring staff.",
        "Visitor badge log updated at front reception desk.",
        "Aarav Waxworks sales rep stopped by to drop off autumn festival greeting calendar.",
        "Packing tape supplier invoice approved and filed with accounts.",
        "Studio espresso machine descaled and restocked with dark roast beans.",
        "Fire extinguisher quarterly inspection certificate renewed by civil inspector.",
    ],
    "northlight-studio": [
        "Figma enterprise license seat count audited ahead of quarterly billing.",
        "Design sprint whiteboard markers restocked in conference room B.",
        "Team Friday demo lunch: Thai curry ordered for 12 team members.",
        "Acoustic panel mounting completed in primary client call booth.",
        "MacBook Pro battery service scheduled for lead mobile engineer.",
        "Office landlord sent notification about air conditioning servicing on Sunday.",
        "Annual SOC2 type II audit preparation checklist shared with leadership.",
        "Standing desk converter assembled in workspace bay 3.",
        "Design agency showcase award submission finalized for UX Design Awards.",
        "Coffee grinder adjusted for French press brew preference.",
        "Guest Wi-Fi network password rotated for monthly security protocol.",
        "Ergonomic chair delivered for newly joined senior interface designer.",
        "Client gift hampers for Diwali curated and supplier quotation requested.",
        "Monitor calibration spider tool checked out by brand identity lead.",
        "Notion workspace permission audit completed across all active client teams.",
    ],
    "brew-lane-cafe": [
        "Marco cleaned and recalibrated the Mazzer espresso grinder burrs at opening.",
        "New ceramic pour-over drippers unpacked and washed for brew bar display.",
        "Local organic honey vendor dropped off tasting samples for seasonal drinks.",
        "Outdoor sidewalk seating permit renewed with municipal ward office.",
        "Sound system playlist updated with low-tempo jazz for weekday morning service.",
        "Refrigerated display case glass seal replaced by technician.",
        "Staff meeting held to review oat milk latte art standards and steaming temps.",
        "Dishwasher rinse aid tank refilled before busy Sunday brunch shift.",
        "Apron laundry delivery arrived with 30 fresh embroidered linen aprons.",
        "Ice machine quarterly sanitize cycle run overnight without disruption.",
        "Food safety inspection completed with zero citations and Grade A rating.",
        "Table 4 wobbly leg fixed with adjustable rubber foot pad.",
        "Custom branded paper takeaway cups restocked from local packaging distributor.",
        "Barista training manual printed and bound for two new trainee hires.",
        "Fire exit door alarm tested during routine weekly facilities inspection.",
    ],
}


def compute_synthetic_actual(
    business: Business,
    decision: Decision,
    ground_truth: dict[str, Any],
    rng: random.Random,
    week: int,
    confounded: bool = False,
    confounder_type: str = "festival",
) -> tuple[float, float, list[str]]:
    """Generate realistic actual outcome from ground truth parameters with noise.

    Returns:
        (actual_effect_in_inr, observed_unit_change_percent, tags)
    """
    g = business.group(decision.group)
    tags: list[str] = []

    # Determine ground truth elasticity
    if "premium" in g.key:
        true_e = ground_truth.get("premium_elasticity", -0.52)
    elif "core" in g.key:
        true_e = ground_truth.get("core_elasticity", -1.74)
    elif "retainer" in g.key:
        true_e = ground_truth.get("retainer_elasticity", -0.42)
    elif "project" in g.key:
        true_e = ground_truth.get("project_elasticity", -1.32)
    elif "dine" in g.key:
        true_e = ground_truth.get("weekend_dinein_elasticity", -0.58)
    else:
        true_e = ground_truth.get("weekday_dinner_elasticity", -1.14)

    noise = rng.gauss(0, 0.035)

    if decision.lever == "price":
        unit_ratio = (1.0 + decision.change) ** true_e - 1.0 + noise
        if confounded:
            if confounder_type == "festival":
                lift = ground_truth.get("festival_lift_factor", 1.45) - 1.0
                unit_ratio = (1.0 + decision.change) ** true_e * (1.0 + lift) - 1.0 + noise
                tags.extend(["confounder", "festival", "diwali rush"])
            else:
                unit_ratio += rng.gauss(0.15, 0.05)
                tags.extend(["confounder", "unusual", "competitor stockout"])
        else:
            tags.append("clean")

        new_units = max(0.0, g.base_units * (1.0 + unit_ratio))
        new_price = g.price * (1.0 + decision.change)
        base_profit = g.base_units * (g.price - g.cogs)
        new_profit = new_units * (new_price - g.cogs)
        weekly_profit_delta = new_profit - base_profit
        actual_effect = weekly_profit_delta * decision.duration + rng.gauss(0, 500)
        unit_change_pct = unit_ratio * 100.0

    elif decision.lever == "ads":
        base_share = g.ad_share
        ad_mult = (1.0 + decision.change) ** 0.45
        unit_ratio = base_share * (ad_mult - 1.0) + noise
        if confounded:
            tags.extend(["confounder", "ad issue", "tracking glitch"])
            unit_ratio *= 0.3
        else:
            tags.append("clean")
        new_units = max(0.0, g.base_units * (1.0 + unit_ratio))
        extra_ad_cost = g.ad_spend * decision.change * (decision.duration / 4.0)
        extra_margin = (new_units - g.base_units) * (g.price - g.cogs) * decision.duration
        actual_effect = extra_margin - extra_ad_cost + rng.gauss(0, 800)
        unit_change_pct = unit_ratio * 100.0

    elif decision.lever == "promotion":
        lift = 1.8 * decision.change + noise
        if confounded:
            tags.extend(["confounder", "weather", "monsoon storm"])
            lift *= 0.4
        else:
            tags.append("clean")
        new_units = g.base_units * (1.0 + lift)
        disc_price = g.price * (1.0 - decision.change)
        base_profit = g.base_units * (g.price - g.cogs)
        new_profit = new_units * (disc_price - g.cogs)
        actual_effect = (new_profit - base_profit) * decision.duration + rng.gauss(0, 600)
        unit_change_pct = lift * 100.0

    else:  # restock
        actual_effect = rng.gauss(5000, 1500)
        unit_change_pct = 0.0
        tags.append("restock")

    return round(actual_effect, -2), round(unit_change_pct, 1), tags


async def seed_world(world_id: str, seed: int = 42017) -> dict[str, Any]:
    print(f"\n=======================================================")
    print(f"Seeding World: {world_id} (Seed: {seed})")
    print(f"=======================================================")

    rng = random.Random(seed)
    ground_truth = TRUTHS[world_id]

    # Save ground truth file
    gt_file = DATA_DIR / f"ground_truth_{world_id}.json"
    gt_file.write_text(json.dumps(ground_truth, indent=2), encoding="utf-8")
    if world_id == "ember-wick":
        (DATA_DIR / "ground_truth.json").write_text(json.dumps(ground_truth, indent=2), encoding="utf-8")

    # Configure business, DB, and Hindsight
    if world_id == "ember-wick":
        business = ember_wick_business()
        db_path = "whatif.db"
        bank_id = "whatif-ember-wick"
        n_decisions = 30
        n_promises = 60
        now_week = 18
    elif world_id == "northlight-studio":
        business = northlight_studio_business()
        db_path = "whatif-northlight-studio.db"
        bank_id = "whatif-northlight-studio"
        n_decisions = 18
        n_promises = 25
        now_week = 14
    else:  # brew-lane-cafe
        business = brew_lane_cafe_business()
        db_path = "whatif-brew-lane-cafe.db"
        bank_id = "whatif-brew-lane-cafe"
        n_decisions = 20
        n_promises = 20
        now_week = 15

    # Clean database initialization without deleting file (avoids Windows lock)
    store = Store(db_path)
    store.initialize()
    with store.lock, store.connection() as db:
        db.execute("DELETE FROM decisions")
        db.execute("DELETE FROM promises")
        db.execute("DELETE FROM memory_events")
    store.set_business(business)
    store.put_setting("beliefs", initial_beliefs(business))
    store.put_setting("week", now_week)

    memory = HindsightMemory(store, bank_id=bank_id, bank_name=f"WHATIF · {business.name}")
    await memory.aensure_bank()

    print(f"[{world_id}] Initialized store at {db_path} and verified Hindsight bank '{bank_id}'")

    # 1. Retain Distractors (15 per world) via batch
    distractors = DISTRACTORS[world_id]
    print(f"[{world_id}] Retaining {len(distractors)} distractors via batch...")
    distractor_batch = []
    for idx, note in enumerate(distractors):
        ts = (START_DATE + timedelta(days=idx * 7 + 2)).isoformat()
        distractor_batch.append({
            "content": note,
            "document_id": f"NOTE-{idx+1:03d}",
            "tags": ["note", "operations", "distractor"],
            "timestamp": ts,
            "context": "WHATIF note",
        })
    await memory.aretain_batch(distractor_batch, retain_async=True)

    # 2. Seed Partner Promises
    partners = business.partners
    print(f"[{world_id}] Generating and resolving {n_promises} partner promises...")
    hedge_words = ["should be", "hopefully", "expect", "planning to be", ""]

    promise_retains = []
    for p_idx in range(n_promises):
        partner = partners[p_idx % len(partners)]
        hedge = hedge_words[p_idx % len(hedge_words)]
        week = p_idx % 52
        quote = f"{partner.name}: order {hedge} ready in {partner.promised_days:.0f} days." if hedge else f"{partner.name}: confirmed delivery in {partner.promised_days:.0f} days."

        # Calculate actual delivery days using hidden ground truth
        promised_d = partner.promised_days
        if partner.key == "rajan-jars":
            ratio = ground_truth.get("rajan_jars_ratio", 1.6)
            extra = ground_truth.get("hedge_extra_days", 3.0) if hedge else 0.0
            actual_d = max(1.0, round(promised_d * ratio + extra + rng.gauss(0, 1.2), 1))
        elif partner.key == "speedy-courier":
            ratio = ground_truth.get("speedy_courier_ratio", 1.7)
            actual_d = max(1.0, round(promised_d * ratio + (2.0 if hedge else 0) + rng.gauss(0, 0.8), 1))
        elif partner.key == "apex-digital":
            actual_d = max(20.0, round(ground_truth.get("apex_digital_payment_days", 47.0) + rng.gauss(0, 4.0), 1))
        elif partner.key == "scaleco":
            actual_d = max(30.0, round(ground_truth.get("scaleco_payment_days", 62.0) + rng.gauss(0, 5.0), 1))
        elif partner.key == "devcraft-contractors":
            ratio = ground_truth.get("devcraft_contractor_ratio", 2.0)
            extra = ground_truth.get("contractor_hedge_extra_days", 4.0) if hedge else 0.0
            actual_d = max(3.0, round(promised_d * ratio + extra + rng.gauss(0, 1.5), 1))
        elif partner.key == "freshfarms-produce":
            delay = ground_truth.get("freshfarms_produce_delay_days", 0.8)
            actual_d = max(1.0, round(promised_d + delay + rng.gauss(0, 0.2), 1))
        elif partner.key == "app-payouts":
            actual_d = max(7.0, round(ground_truth.get("delivery_app_payout_days", 16.0) + rng.gauss(0, 1.5), 1))
        else:
            actual_d = max(1.0, round(promised_d * (1.1 if hedge else 1.0) + rng.gauss(0, 0.5), 1))

        promise_id = f"P-{p_idx+1:04d}"
        created_at = (START_DATE + timedelta(days=p_idx * 5)).isoformat()
        item = {
            "id": promise_id,
            "partner_key": partner.key,
            "item": "batch order / delivery",
            "quote": quote,
            "promised_days": promised_d,
            "hedged": bool(hedge),
            "created_at": created_at,
        }
        store.add_promise(item)

        # Batch retain promise
        promise_retains.append({
            "content": f"Promise {promise_id}: {partner.name} promised in {promised_d:.0f} days. Quote: \"{quote}\"",
            "document_id": promise_id,
            "tags": ["promise", f"partner:{partner.key}", "hedged" if hedge else "firm"],
            "timestamp": created_at,
            "context": "WHATIF promise",
        })

        # Deliver promise
        store.deliver_promise(promise_id, actual_d)
        beliefs = store.beliefs()
        update_partner(beliefs, f"partner:{partner.key}", promised_d, actual_d, bool(hedge), "resolved promise")
        store.set_beliefs(beliefs)

        # Batch retain resolution
        resolved_ts = (START_DATE + timedelta(days=p_idx * 5 + int(actual_d))).isoformat()
        promise_retains.append({
            "content": f"Promise {promise_id} resolved: {partner.name} delivered in {actual_d:.1f} days (promised {promised_d:.0f} days, hedged: {bool(hedge)}).",
            "document_id": promise_id,
            "tags": ["promise", f"partner:{partner.key}", "status:resolved"],
            "timestamp": resolved_ts,
            "context": "WHATIF promise",
        })

    # Retain promises in chunks of 20
    for chunk_start in range(0, len(promise_retains), 20):
        chunk = promise_retains[chunk_start : chunk_start + 20]
        await memory.aretain_batch(chunk, retain_async=True)

    # Cold start partner: joins late
    cold_partner_name = "CraftBox Luxe" if world_id == "ember-wick" else ("CloudForge DevOps" if world_id == "northlight-studio" else "Artisan Bakes")
    cold_partner_key = "craftbox-luxe" if world_id == "ember-wick" else ("cloudforge-devops" if world_id == "northlight-studio" else "artisan-bakes")
    cold_promise_id = f"P-COLD-01"
    cold_created_at = (START_DATE + timedelta(weeks=45)).isoformat()
    store.add_promise({
        "id": cold_promise_id,
        "partner_key": cold_partner_key,
        "item": "first trial batch delivery",
        "quote": f"{cold_partner_name}: we can deliver trial run within 7 business days.",
        "promised_days": 7.0,
        "hedged": False,
        "created_at": cold_created_at,
    })
    await memory.aretain(
        "promise",
        cold_promise_id,
        f"Promise {cold_promise_id}: New supplier {cold_partner_name} onboarded late with zero delivery history.",
        ["promise", f"partner:{cold_partner_key}", "cold-start"],
        cold_created_at,
    )
    print(f"[{world_id}] Planted cold-start partner: {cold_partner_name}")

    # 3. Seed Decisions & Reviews (The real product loop)
    print(f"[{world_id}] Running real product loop for {n_decisions} decisions...")
    group_keys = [g.key for g in business.groups]

    # Pre-configure scripted decisions
    scripted_decisions = []
    for d_idx in range(n_decisions):
        group = group_keys[d_idx % len(group_keys)]
        lever = ["price", "ads", "promotion", "price", "ads", "restock"][d_idx % 6]
        start_wk = 1
        duration = 4

        if lever == "price":
            change = 0.08 if d_idx % 2 == 0 else 0.10
        elif lever == "ads":
            change = 0.25 if d_idx % 2 == 0 else -0.20
        elif lever == "promotion":
            change = 0.15
            duration = 2
        else:  # restock
            change = 500
            duration = 1

        scripted_decisions.append({
            "idx": d_idx + 1,
            "lever": lever,
            "group": group,
            "change": change,
            "start": start_wk,
            "duration": duration,
        })

    # Plant deliberate features:
    # Feature 2: Conflicting precedent
    # Precedent A (clean core price hike in normal week)
    # Precedent B (confounded core price hike during festival rush)
    # Feature 4: Noisy review (high uncertainty, wide attribution band)
    for d_spec in scripted_decisions:
        d_idx = d_spec["idx"]
        dec = Decision(
            lever=d_spec["lever"],
            group=d_spec["group"],
            change=d_spec["change"],
            start=d_spec["start"],
            duration=d_spec["duration"],
        )
        sim_week = (d_idx * 1) % 50
        beliefs_current = store.beliefs()

        # Run simulate()
        sim_res, _ = simulate(business, beliefs_current, dec, now_week=sim_week, seed=seed + d_idx)
        dec_id = f"D-{d_idx:03d}"
        created_at = (START_DATE + timedelta(weeks=sim_week)).isoformat()
        rev_date = (START_DATE + timedelta(weeks=sim_week + dec.duration)).isoformat()

        # Decide if this decision is confounded or noisy
        is_conflicted_b = (d_idx == 12 and dec.lever == "price")
        is_noisy_review = (d_idx == 8)
        confounded = is_conflicted_b or is_noisy_review or (d_idx in {19, 26})
        confounder_type = "festival" if is_conflicted_b else "noise"

        # Generate actual effect from ground truth
        actual_effect, unit_pct, tags = compute_synthetic_actual(
            business, dec, ground_truth, rng, sim_week, confounded=confounded, confounder_type=confounder_type
        )

        uncertainty = 0.25 if is_noisy_review else (0.18 if confounded else 0.08)
        if is_noisy_review:
            tags.extend(["confounder", "unusual", "severe monsoon flood & road blockage"])

        # Commit decision
        clear_bet = sim_res["plan"]["profit_delta"]["p50"] > 0 and sim_res["plan"]["loss_chance"] < 0.45
        hypothesis = (
            f"{title_for(dec)} improves profit without a harmful cash dip."
            if clear_bet
            else f"Test whether {title_for(dec)} avoids a harmful cash dip despite uncertain return."
        )
        commit_item = {
            "id": dec_id,
            "title": title_for(dec),
            "payload": {**dec.as_dict(), "hypothesis": hypothesis, "success_rule": "Actual result lands inside 80% range."},
            "prediction": sim_res,
            "memory_on": True,
            "status": "committed",
            "created_at": created_at,
            "review_date": rev_date,
        }
        store.add_decision(commit_item)

        await memory.aretain(
            "decision",
            dec_id,
            decision_memory_text(dec_id, dec, sim_res, "committed"),
            ["decision", f"lever:{dec.lever}", f"group:{dec.group}", "status:committed"],
            created_at,
            retain_async=True,
        )

        # Review decision
        review_outcome = review(
            business=business,
            beliefs=beliefs_current,
            decision=dec,
            prediction=sim_res,
            actual_effect=actual_effect,
            observed_unit_change=unit_pct,
            tags=tags,
            uncertainty=uncertainty,
        )

        if review_outcome["learned"]:
            store.set_beliefs(beliefs_current)

        store.review_decision(dec_id, review_outcome)

        await memory.aretain(
            "review",
            dec_id,
            decision_memory_text(dec_id, dec, sim_res, "reviewed", review_outcome),
            ["decision", f"lever:{dec.lever}", f"group:{dec.group}", "status:reviewed"],
            rev_date,
            retain_async=True,
        )

    scorecard = store.scorecard()
    cov_str = f"{scorecard['coverage']:.1%}" if scorecard["coverage"] is not None else "N/A"
    print(f"[{world_id}] Seeding complete!")
    print(f"[{world_id}] Scorecard: {scorecard['reviews']} reviews, {scorecard['gradable_reviews']} gradable, Coverage: {cov_str}")
    return {
        "world_id": world_id,
        "business": business.name,
        "decisions": len(store.list_decisions()),
        "promises": len(store.list_promises()),
        "scorecard": scorecard,
    }


async def bank_saved_runs() -> list[dict[str, Any]]:
    print("\n=======================================================")
    print("Banking Saved Runs Library (18 runs total, 6 per world)")
    print("=======================================================")

    questions_by_world = {
        "ember-wick": [
            "Raise Premium prices 10% for 4 weeks",
            "Cut Instagram ads by 20% for 6 weeks",
            "Run a 15% weekend flash sale on Core range for 2 weeks",
            "Restock 2500 jars from Rajan Jars",
            "Raise Core range prices 8% for 4 weeks",
            "Increase Instagram ads by 35% for 4 weeks",
        ],
        "northlight-studio": [
            "Raise retainer rates by 10% for 4 weeks",
            "Offer 15% discount on fixed-price projects for 4 weeks",
            "Increase LinkedIn lead-gen ads by 50% for 4 weeks",
            "Hire contractor capacity with 300 project units",
            "Raise fixed-price project rates by 12% for 4 weeks",
            "Cut marketing spend by 40% for 6 weeks",
        ],
        "brew-lane-cafe": [
            "Increase dine-in menu prices by 8% for 4 weeks",
            "Offer 20% weekday promotion on dine-in for 2 weeks",
            "Increase delivery promotion ads by 30% for 4 weeks",
            "Restock 1500 produce batches from FreshFarms",
            "Lower delivery prices by 5% for 4 weeks",
            "Cut ad spend by 25% for 4 weeks",
        ],
    }

    saved_runs = []
    run_idx = 1

    for world_id, questions in questions_by_world.items():
        db_path = "whatif.db" if world_id == "ember-wick" else f"whatif-{world_id}.db"
        bank_id = f"whatif-{world_id}"
        store = Store(db_path)
        business = store.business()
        memory = HindsightMemory(store, bank_id=bank_id)

        for q in questions:
            dec = parse_question(q, business)

            for memory_on in (True, False):
                t0 = time.perf_counter()
                beliefs = store.beliefs() if memory_on else initial_beliefs(business)
                sim_res, _ = simulate(business, beliefs, dec, now_week=store.week(), seed=42000 + run_idx)

                # Query memory if on
                recalled = await memory.arecall(f"{dec.lever} decision for {dec.group}: {title_for(dec)}", ["decision"], memory_on=memory_on)
                latency_ms = round((time.perf_counter() - t0) * 1000, 1)

                record = {
                    "run_id": f"SR-{run_idx:03d}",
                    "world_id": world_id,
                    "business": business.name,
                    "question": q,
                    "decision": dec.as_dict(),
                    "seed": 42000 + run_idx,
                    "memory_on": memory_on,
                    "timestamp": utcnow(),
                    "response_time_ms": latency_ms,
                    "profit_delta": sim_res["plan"]["profit_delta"],
                    "loss_chance": sim_res["plan"]["loss_chance"],
                    "min_cash": sim_res["plan"]["cash"]["min_p50"],
                    "min_week": sim_res["plan"]["cash"]["min_week"],
                    "negative_cash_chance": sim_res["plan"]["cash"]["negative_chance"],
                    "recommendation": "test" if sim_res["test"]["recommended"] else "plan",
                    "citations_count": len(recalled.get("items", [])),
                }
                saved_runs.append(record)
                run_idx += 1

    out_file = DATA_DIR / "saved_runs.json"
    out_file.write_text(json.dumps(saved_runs, indent=2), encoding="utf-8")
    print(f"Saved {len(saved_runs)} runs to {out_file}")
    return saved_runs


async def run_diwali_10_seed_rehearsal() -> list[dict[str, Any]]:
    print("\n=======================================================")
    print("Running 10-Seed Stability Rehearsal: Hard Diwali Compound Scenario")
    print("=======================================================")

    store = Store("whatif.db")
    business = store.business()
    beliefs = store.beliefs()
    clean_beliefs = initial_beliefs(business)
    memory = HindsightMemory(store, bank_id="whatif-ember-wick")

    hard_q = "Diwali Campaign: Core price +8%, Ads +2L, restock 4,000 jars from Rajan Jars"
    dec = parse_question(hard_q, business)

    rehearsal_results = []

    for seed in range(1, 11):
        t0 = time.perf_counter()
        res_mem_on, _ = simulate(business, beliefs, dec, now_week=18, seed=seed)
        recalled = await memory.arecall(f"{dec.lever} decision for {dec.group}: {title_for(dec)}", ["decision"], memory_on=True)
        lat_on = round((time.perf_counter() - t0) * 1000, 1)

        t1 = time.perf_counter()
        res_mem_off, _ = simulate(business, clean_beliefs, dec, now_week=18, seed=seed)
        lat_off = round((time.perf_counter() - t1) * 1000, 1)

        row = {
            "seed": seed,
            "memory_on": {
                "profit_p10": res_mem_on["plan"]["profit_delta"]["p10"],
                "profit_p50": res_mem_on["plan"]["profit_delta"]["p50"],
                "profit_p90": res_mem_on["plan"]["profit_delta"]["p90"],
                "loss_chance": res_mem_on["plan"]["loss_chance"],
                "min_cash_p50": res_mem_on["plan"]["cash"]["min_p50"],
                "min_week": res_mem_on["plan"]["cash"]["min_week"],
                "negative_cash_chance": res_mem_on["plan"]["cash"]["negative_chance"],
                "test_min_cash_p50": res_mem_on["test"]["cash"]["min_p50"],
                "latency_ms": lat_on,
                "recalled_items_count": len(recalled.get("items", [])),
            },
            "memory_off": {
                "profit_p10": res_mem_off["plan"]["profit_delta"]["p10"],
                "profit_p50": res_mem_off["plan"]["profit_delta"]["p50"],
                "profit_p90": res_mem_off["plan"]["profit_delta"]["p90"],
                "loss_chance": res_mem_off["plan"]["loss_chance"],
                "min_cash_p50": res_mem_off["plan"]["cash"]["min_p50"],
                "min_week": res_mem_off["plan"]["cash"]["min_week"],
                "negative_cash_chance": res_mem_off["plan"]["cash"]["negative_chance"],
                "latency_ms": lat_off,
            },
        }
        rehearsal_results.append(row)
        print(f"Seed {seed:02d}: MemOn p50=₹{row['memory_on']['profit_p50']:,.0f}, MinCash=₹{row['memory_on']['min_cash_p50']:,.0f} (Wk {row['memory_on']['min_week']}), NegChance={row['memory_on']['negative_cash_chance']:.0%} | Latency={lat_on}ms")

    out_file = DATA_DIR / "diwali_rehearsal_seeds.json"
    out_file.write_text(json.dumps(rehearsal_results, indent=2), encoding="utf-8")
    print(f"Wrote 10-seed rehearsal data to {out_file}")
    return rehearsal_results


async def run_verification_queries():
    print("\n=======================================================")
    print("Running Verification Queries Across Banks")
    print("=======================================================")

    store_candle = Store("whatif.db")
    store_cafe = Store("whatif-brew-lane-cafe.db")

    mem_candle = HindsightMemory(store_candle, bank_id="whatif-ember-wick")
    mem_cafe = HindsightMemory(store_cafe, bank_id="whatif-brew-lane-cafe")

    # 1. Precision check: Query candle price in candle bank
    res_precision = await mem_candle.arecall("past price changes on core range", tags=["decision", "lever:price"])
    candle_items = res_precision.get("items", [])
    distractor_hits = [it for it in candle_items if "note" in it.get("tags", []) or any(d in it.get("text", "") for d in ["cupcake", "printer", "Wi-Fi"])]
    print(f"Precision Check (Candle Bank): {len(candle_items)} results returned. Distractor hits: {len(distractor_hits)} (Expect: 0)")

    # 2. Isolation check: Query candle pricing in café bank
    res_isolation = await mem_cafe.arecall("past candle price changes on core range", tags=["decision", "lever:price"])
    cafe_items = res_isolation.get("items", [])
    candle_leaks = [it for it in cafe_items if any(w in it.get("text", "").lower() for w in ["candle", "wick", "rajan", "aarav"])]
    print(f"Isolation Check (Café Bank querying Candle): {len(cafe_items)} results returned. Candle leaks: {len(candle_leaks)} (Expect: 0)")

    # 3. Partner memory check: Rajan Jars delivery
    res_partner = await mem_candle.arecall("Rajan Jars delivery lead time and delay", tags=["promise", "partner:rajan-jars"])
    partner_items = res_partner.get("items", [])
    print(f"Partner Memory Check (Rajan Jars): {len(partner_items)} items returned with delivery quotes.")

    # 4. Reflection check
    res_reflect = await mem_candle.areflect("Why were past forecasts off or uncertain?", tags=["decision", "status:reviewed"])
    print(f"Reflection Check (Synthesized text length: {len(res_reflect.get('text', ''))} chars):")
    print(f"Summary: {res_reflect.get('text', '')[:200]}...")

    return {
        "precision": {"results": len(candle_items), "distractor_hits": len(distractor_hits)},
        "isolation": {"results": len(cafe_items), "candle_leaks": len(candle_leaks)},
        "partner": {"results": len(partner_items)},
        "reflection": res_reflect,
    }


async def main():
    print("Starting Synthetic Worlds Seeding & Validation Pipeline...")
    t_start = time.perf_counter()

    # Seed all three worlds
    for world_id in ("ember-wick", "northlight-studio", "brew-lane-cafe"):
        await seed_world(world_id)

    # Bank saved runs library
    await bank_saved_runs()

    # Run 10-seed rehearsal for hard Diwali scenario
    await run_diwali_10_seed_rehearsal()

    # Run verification queries
    await run_verification_queries()

    total_time = round(time.perf_counter() - t_start, 1)
    print(f"\n=======================================================")
    print(f"Pipeline Completed in {total_time}s!")
    print(f"=======================================================")


if __name__ == "__main__":
    asyncio.run(main())
