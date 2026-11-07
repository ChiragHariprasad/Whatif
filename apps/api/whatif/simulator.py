from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Any

import numpy as np

from .beliefs import H_GRID, K_GRID, hill
from .config import Business, LEVERS

DEFAULT_RUNS = 5000
HORIZON = 13


@dataclass
class Decision:
    lever: str
    group: str
    change: float
    start: int = 1
    duration: int = 4
    title: str | None = None
    linked_decisions: list[Decision] = field(default_factory=list)
    horizon: int = HORIZON

    @property
    def end(self) -> int:
        return min(self.horizon, self.start + self.duration)

    @property
    def eval_end(self) -> int:
        return min(self.horizon, self.end + (2 if self.lever == "promotion" else 0))

    def active(self, week: int) -> bool:
        return self.start <= week < self.end

    @property
    def all_decisions(self) -> list[Decision]:
        return [self] + list(self.linked_decisions or [])

    def as_dict(self) -> dict[str, Any]:
        res = {"lever": self.lever, "group": self.group, "change": self.change, "start": self.start, "duration": self.duration, "title": self.title or title_for(self)}
        if self.linked_decisions:
            res["linked_decisions"] = [ld.as_dict() for ld in self.linked_decisions]
        return res


def title_for(decision: Decision) -> str:
    target = decision.group.replace("_", " ").title()
    if decision.lever == "price": return f"Change {target} price by {decision.change * 100:+.0f}%"
    if decision.lever == "ads": return f"Change {target} ads by {decision.change * 100:+.0f}%"
    if decision.lever == "promotion": return f"Run a {decision.change * 100:.0f}% {target} promotion"
    return f"Restock {target} with {decision.change:.0f} extra units"


def test_decision(decision: Decision, business: Business) -> Decision:
    if decision.linked_decisions:
        linked = []
        for ld in decision.linked_decisions:
            if ld.lever == "ads":
                linked.append(Decision("ads", ld.group, min(ld.change * .4, .20), ld.start, 2, title="Capped ad test", horizon=decision.horizon))
            elif ld.lever == "restock":
                min_units = max(1, round(business.group(ld.group).base_units * .2))
                linked.append(Decision("restock", ld.group, max(min_units, round(ld.change * .25)), ld.start, 1, title="Split order (batch 1)", horizon=decision.horizon))
            else:
                linked.append(test_decision(replace(ld, horizon=decision.horizon), business))
        return Decision(decision.lever, decision.group, decision.change * .5, decision.start, 2, title="Smaller test: split restock & cap ads", linked_decisions=linked, horizon=decision.horizon)
    if decision.lever == "restock":
        change = max(1, round(decision.change * .5))
    else:
        change = decision.change * .5
    return Decision(decision.lever, decision.group, change, decision.start, max(2, min(decision.duration, 2)), title="Smaller test", horizon=decision.horizon)


def parse_question(question: str, business: Business) -> Decision:
    """Small deterministic parser; the API also returns the editable decision card."""
    import re
    lower = question.lower()
    group_keys = [g.key for g in business.groups]
    group = group_keys[0]
    for g in business.groups:
        if g.key.lower() in lower or any(w in lower for w in g.name.lower().split() if len(w) > 3):
            group = g.key
            break
    if "premium" in lower and "premium" in group_keys: group = "premium"
    elif "core" in lower and "core" in group_keys: group = "core"
    elif "gift" in lower and "gifting" in group_keys: group = "gifting"
    elif any(w in lower for w in ("retainer", "retainers")) and "retainers" in group_keys: group = "retainers"
    elif any(w in lower for w in ("project", "projects", "fixed-price", "fixed price")) and "projects" in group_keys: group = "projects"
    elif any(w in lower for w in ("dine-in", "dine in", "dining", "menu")) and "dine_in" in group_keys: group = "dine_in"
    elif any(w in lower for w in ("delivery", "app", "online")) and "delivery" in group_keys: group = "delivery"
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*%", lower)
    percent = float(match.group(1)) / 100 if match else .10
    duration = int(re.search(r"(\d+)\s*(?:week|wk)", lower).group(1)) if re.search(r"(\d+)\s*(?:week|wk)", lower) else 4
    # A campaign can contain several levers. Extract the values from the text
    # rather than substituting a candle-specific preset.
    has_price = any(x in lower for x in ("price", "rate", "raise"))
    has_ads = any(x in lower for x in ("ad", "advert", "instagram", "spend", "linkedin"))
    has_restock = any(x in lower for x in ("restock", "reorder", "inventory", "stock"))
    if sum((has_price, has_ads, has_restock)) >= 2:
        percentages = [float(value) / 100 for value in re.findall(r"([+-]?\d+(?:\.\d+)?)\s*%", lower)]
        price_change = percentages[0] if percentages else .10
        ad_change = percentages[1] if len(percentages) > 1 else .20
        money_match = re.search(r"([+-]?\d+(?:\.\d+)?)\s*(?:l|lakh)\b", lower)
        if has_ads and money_match:
            ad_change = float(money_match.group(1)) * 100000 / max(business.monthly_ad_spend, 1)
        restock_match = re.search(r"([\d,]+)\s*(?:unit|jar|piece|project|team|order)", lower)
        restock_change = float(restock_match.group(1).replace(",", "")) if restock_match else max(1, round(business.group(group).base_units * .25))
        restock_group = group
        restock_clause = lower[lower.find("restock"):] if "restock" in lower else lower
        for candidate in business.groups:
            supplier = business.partner(candidate.supplier)
            if candidate.key in restock_clause or any(word in restock_clause for word in candidate.name.lower().split() if len(word) > 3) or supplier.key.split("-")[0] in restock_clause:
                restock_group = candidate.key
                break
        linked: list[Decision] = []
        primary = "price" if has_price else ("ads" if has_ads else "restock")
        if has_price and primary != "price": linked.append(Decision("price", group, price_change, duration=duration, title=f"Price change {price_change:+.0%}"))
        if has_ads and primary != "ads": linked.append(Decision("ads", group, ad_change, duration=duration, title=f"Ad change {ad_change:+.0%}"))
        if has_restock and primary != "restock": linked.append(Decision("restock", restock_group, restock_change, duration=1, title=f"Restock {restock_change:.0f} units"))
        primary_change = price_change if primary == "price" else (ad_change if primary == "ads" else restock_change)
        return Decision(primary, restock_group if primary == "restock" else group, primary_change, duration=1 if primary == "restock" else duration, title="Multi-lever campaign", linked_decisions=linked)
    if any(x in lower for x in ("price", "raise", "increase price", "cheaper")):
        if any(x in lower for x in ("discount", "off", "sale", "promo")): return Decision("promotion", group, abs(percent), duration=duration)
        sign = -1 if any(x in lower for x in ("lower", "reduce", "decrease")) else 1
        return Decision("price", group, sign * abs(percent), duration=duration)
    if any(x in lower for x in ("ad", "advert", "instagram", "spend")):
        sign = -1 if any(x in lower for x in ("lower", "reduce", "decrease")) else 1
        return Decision("ads", group, sign * abs(percent), duration=duration)
    if any(x in lower for x in ("promo", "discount", "sale", "offer")):
        return Decision("promotion", group, abs(percent), duration=duration)
    if any(x in lower for x in ("restock", "reorder", "inventory", "stock")):
        amount = float(re.search(r"([\d,]+)\s*(?:unit|jar|piece|project|team|order)", lower).group(1).replace(",", "")) if re.search(r"([\d,]+)\s*(?:unit|jar|piece|project|team|order)", lower) else max(1, round(business.group(group).base_units * .25))
        return Decision("restock", group, amount, duration=1)
    return Decision("price", group, .10, duration=duration)


def _world(business: Business, beliefs: dict[str, dict[str, Any]], n: int, seed: int, horizon: int) -> dict[str, Any]:
    rng = np.random.default_rng(seed); groups = business.groups; g_count = len(groups)
    elasticity = np.empty((n, g_count)); ad_shape = np.empty((n, g_count)); ad_half = np.empty((n, g_count))
    promo_lift = np.empty((n, g_count)); promo_pull = np.empty((n, g_count))
    for i, group in enumerate(groups):
        eb = beliefs[f"elasticity:{group.key}"]; elasticity[:, i] = rng.normal(eb["mean"], max(eb["sd"], .04), n)
        ab = beliefs[f"ad:{group.key}"]; weights = np.asarray(ab["weights"]); choices = rng.choice(len(weights), n, p=weights / weights.sum())
        ad_shape[:, i] = H_GRID[choices // len(K_GRID)]; ad_half[:, i] = K_GRID[choices % len(K_GRID)]
        lb = beliefs[f"promo_lift:{group.key}"]; pb = beliefs[f"promo_pull:{group.key}"]
        promo_lift[:, i] = np.clip(rng.normal(lb["mean"], max(lb["sd"], .03), n), 0, 1.6)
        promo_pull[:, i] = np.clip(rng.normal(pb["mean"], max(pb["sd"], .04), n), 0, 1.2)
    ratios = {}
    for partner in business.partners:
        b = beliefs[f"partner:{partner.key}"]
        ratios[partner.key] = np.exp(rng.normal(b["mean"], max(b.get("sigma", .15), .04), (n, horizon)))
    return {"rng": rng, "elasticity": elasticity, "ad_shape": ad_shape, "ad_half": ad_half, "promo_lift": promo_lift, "promo_pull": promo_pull, "ratios": ratios,
            "demand_noise": np.exp(rng.normal(0, .065, (n, horizon, g_count))), "level": np.exp(rng.normal(0, .04, (n, 1))) }


def _scatter(target: np.ndarray, indexes: np.ndarray, values: np.ndarray) -> None:
    rows = np.arange(target.shape[0]); np.add.at(target, (rows, np.clip(indexes, 0, target.shape[1] - 1)), values)


def run_twin(business: Business, world: dict[str, Any], decisions: list[Decision], now_week: int = 0) -> dict[str, Any]:
    n, t_count, groups = world["demand_noise"].shape
    cfg_groups = business.groups; index = {g.key: i for i, g in enumerate(cfg_groups)}
    base = np.array([g.base_units for g in cfg_groups]); price0 = np.array([g.price for g in cfg_groups]); cogs = np.array([g.cogs for g in cfg_groups]); ad0 = np.array([g.ad_spend for g in cfg_groups]); ad_share = np.array([g.ad_share for g in cfg_groups])
    supplier_days = np.array([business.partner(g.supplier).promised_days for g in cfg_groups])
    cover = business.reorder_every + supplier_days / 7 + np.array([g.safety_weeks for g in cfg_groups])
    inventory = np.tile(base * cover, (n, 1)).astype(float)
    arrivals = np.zeros((n, groups, t_count + 10)); receipts_future = np.zeros((n, t_count + 10)); pull_forward = np.zeros((n, groups, t_count + 10))
    cash = np.full(n, float(business.cash0), dtype=float); cash_path = np.empty((n, t_count + 1)); cash_path[:, 0] = cash
    units = np.zeros((n, t_count, groups)); lost = np.zeros_like(units); actual_prices = np.zeros_like(units); actual_ads = np.zeros_like(units); profits = np.zeros((n, t_count)); revenues = np.zeros((n, t_count)); supplier_paid = np.zeros((n, t_count)); receipts = np.zeros((n, t_count))
    for t in range(t_count):
        inventory += arrivals[:, :, t]
        price_ratio, ad_ratio, discount, restock = np.ones(groups), np.ones(groups), np.zeros(groups), np.zeros(groups)
        for decision in decisions:
            i = index[decision.group]
            if decision.lever == "price" and decision.active(t): price_ratio[i] *= 1 + decision.change
            elif decision.lever == "ads" and decision.active(t): ad_ratio[i] *= 1 + decision.change
            elif decision.lever == "promotion" and decision.active(t): discount[i] = max(discount[i], decision.change)
            elif decision.lever == "restock" and t == decision.start: restock[i] += decision.change
        base_demand = base * business.season(now_week + t) * world["level"] * world["demand_noise"][:, t, :]
        organic = base_demand * (1 - ad_share)
        ad_multiplier = hill(ad_ratio[None, :], world["ad_shape"], world["ad_half"]) / hill(1, world["ad_shape"], world["ad_half"])
        demand = organic + base_demand * ad_share * ad_multiplier
        pricing = np.where(discount > 0, 1., price_ratio)[None, :] ** world["elasticity"]
        promotion = np.where(discount > 0, 1 + world["promo_lift"] * discount[None, :] / .10, 1.)
        demand = np.maximum(demand * pricing * promotion - pull_forward[:, :, t], 0)
        sold = np.minimum(demand, inventory); inventory -= sold; units[:, t, :] = sold; lost[:, t, :] = demand - sold
        for decision in decisions:
            if decision.lever == "promotion" and decision.active(t):
                i = index[decision.group]; extra = np.maximum(demand[:, i] - base_demand[:, i], 0) * world["promo_pull"][:, i]
                if decision.end < pull_forward.shape[2]: pull_forward[:, i, decision.end] += extra / 2
                if decision.end + 1 < pull_forward.shape[2]: pull_forward[:, i, decision.end + 1] += extra / 2
        price = price0 * np.where(discount > 0, 1 - discount, price_ratio); ad = ad0 * ad_ratio
        actual_prices[:, t, :] = price; actual_ads[:, t, :] = ad
        revenue = (sold * price).sum(1); revenues[:, t] = revenue
        courier_ratio = world["ratios"][business.courier_key][:, t]; delay = business.partner(business.courier_key).promised_days * courier_ratio / 7
        low = np.floor(delay).astype(int); fraction = delay - low
        delayed_share = business.receipt_delay_share
        _scatter(receipts_future, t + low, delayed_share * revenue * (1 - fraction)); _scatter(receipts_future, t + low + 1, delayed_share * revenue * fraction)
        receipts_future[:, t] += (1 - delayed_share) * revenue
        orders = np.zeros((n, groups))
        if (now_week + t) % business.reorder_every == 0:
            target = base * cover * business.season(now_week + t + 1); pipeline = arrivals[:, :, t + 1:].sum(2)
            orders = np.maximum(target[None, :] - inventory - pipeline, 0)
        orders += restock[None, :]
        for i, group in enumerate(cfg_groups):
            delay = business.partner(group.supplier).promised_days * world["ratios"][group.supplier][:, t] / 7
            low = np.maximum(np.floor(delay).astype(int), 1); fraction = delay - np.floor(delay)
            _scatter(arrivals[:, i, :], t + low, orders[:, i] * (1 - fraction)); _scatter(arrivals[:, i, :], t + low + 1, orders[:, i] * fraction)
        paid = (orders * cogs).sum(1); supplier_paid[:, t] = paid
        cash += receipts_future[:, t] - paid - ad.sum() - business.fixed_weekly
        cash_path[:, t + 1] = cash; receipts[:, t] = receipts_future[:, t]
        profits[:, t] = revenue - (sold * cogs).sum(1) - ad.sum() - business.fixed_weekly
    return {"units": units, "lost": lost, "price": actual_prices, "ads": actual_ads, "profit": profits, "cash": cash_path, "revenue": revenues, "receipts": receipts, "supplier_paid": supplier_paid}


def quantiles(values: np.ndarray) -> dict[str, float]:
    low, mid, high = np.percentile(values, (10, 50, 90)); return {"p10": float(low), "p50": float(mid), "p90": float(high)}


def cash_summary(cash: np.ndarray) -> dict[str, Any]:
    p10, p50, p90 = np.percentile(cash, (10, 50, 90), axis=0); minimums = cash[:, 1:].min(axis=1); min_week = int(np.argmin(p50[1:]) + 1)
    below = np.where(p10[1:] < 0)[0]
    return {"min_p10": float(np.percentile(minimums, 10)), "min_p50": float(np.percentile(minimums, 50)), "min_week": min_week, "min_value": float(p50[min_week]), "runway_weeks": int(below[0] + 1) if len(below) else None, "negative_chance": float((minimums < 0).mean()), "fan": {"p10": p10.tolist(), "p50": p50.tolist(), "p90": p90.tolist()}}


def simulate(business: Business, beliefs: dict[str, dict[str, Any]], decision: Decision, now_week: int = 0,
             seed: int = 17, runs: int = DEFAULT_RUNS, calibration_scale: float = 1., horizon: int = HORIZON) -> tuple[dict[str, Any], dict[str, Any]]:
    """Common random numbers make the scenario comparison stable and interpretable."""
    if decision.lever not in LEVERS: raise ValueError("Unknown lever")
    if decision.group not in [group.key for group in business.groups]: raise ValueError("Unknown product group")
    horizon = max(13, min(52, horizon))
    decision = replace(decision, horizon=horizon, linked_decisions=[replace(item, horizon=horizon) for item in decision.linked_decisions])
    world = _world(business, beliefs, runs, seed, horizon); baseline = run_twin(business, world, [], now_week); test = test_decision(decision, business)
    group_index = [g.key for g in business.groups].index(decision.group); measurement_noise = world["rng"].normal(0, .055, runs)
    def scenario(label: str, d: Decision | None) -> tuple[dict[str, Any], dict[str, Any]]:
        target_decisions = [] if d is None else d.all_decisions
        run = baseline if d is None else run_twin(business, world, target_decisions, now_week); end = (d or decision).eval_end
        profit_delta = run["profit"][:, :end].sum(1) - baseline["profit"][:, :end].sum(1)
        if d is not None: profit_delta += measurement_noise * max(1, business.group(d.group).margin * business.group(d.group).base_units * max(1, d.duration))
        qs = quantiles(profit_delta)
        if calibration_scale != 1:
            qs = {"p10": qs["p50"] - calibration_scale * (qs["p50"] - qs["p10"]), "p50": qs["p50"], "p90": qs["p50"] + calibration_scale * (qs["p90"] - qs["p50"])}
        base_units = np.maximum(baseline["units"][:, :end, group_index].sum(1), 1e-8); units = run["units"][:, :end, group_index].sum(1)
        return {"name": label, "decision": d.as_dict() if d else None, "profit_delta": qs, "loss_chance": float((profit_delta < 0).mean()) if d else 0., "units_pct": quantiles((units / base_units - 1) * 100) if d else {"p10": 0., "p50": 0., "p90": 0.}, "cash": cash_summary(run["cash"]), "stockout_chance": float((run["lost"][:, :end, group_index].sum(1) > .5).mean()), "window_weeks": end}, run
    nothing, _ = scenario("Do nothing", None); plan, plan_run = scenario("Your plan", decision); small_test, _ = scenario("Test first", test)
    plan["recommended"] = plan["loss_chance"] <= small_test["loss_chance"] and plan["profit_delta"]["p50"] > 0
    small_test["recommended"] = not plan["recommended"]
    return {"decision": decision.as_dict(), "now_week": now_week, "horizon": horizon, "runs": runs, "nothing": nothing, "plan": plan, "test": small_test, "assumptions": important_assumptions(business, beliefs, decision), "simulation_seed": seed}, plan_run


def important_assumptions(business: Business, beliefs: dict[str, dict[str, Any]], decision: Decision) -> list[dict[str, Any]]:
    group = business.group(decision.group); output = []
    if decision.lever == "price":
        b = beliefs[f"elasticity:{group.key}"]; output.append({"name": "Price sensitivity", "value": b["mean"], "min": -4, "max": -.02, "unit": "elasticity", "evidence": b["n"]})
    if decision.lever == "ads":
        b = beliefs[f"ad:{group.key}"]; output.append({"name": "Ad saturation", "value": b["mean"], "min": .2, "max": 5, "unit": "× baseline spend", "evidence": b["n"]})
    if decision.lever == "promotion":
        b = beliefs[f"promo_lift:{group.key}"]; output.append({"name": "Promotion lift", "value": b["mean"], "min": 0, "max": 1.5, "unit": "unit lift", "evidence": b["n"]})
    partner = business.partner(group.supplier); b = beliefs[f"partner:{partner.key}"]
    output.append({"name": f"{partner.name} delivery", "value": partner.promised_days * math.exp(b["mean"]), "min": partner.promised_days, "max": partner.promised_days * 3, "unit": "days", "evidence": b["n"]})
    output.append({"name": "Delayed receipts share", "value": business.receipt_delay_share, "min": 0, "max": 1, "unit": "share", "evidence": 0})
    return output[:3]
