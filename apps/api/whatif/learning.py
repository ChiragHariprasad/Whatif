from __future__ import annotations

import math
from typing import Any

from .attribution import score
from .beliefs import normal_update, update_ad
from .config import Business
from .simulator import Decision


def review(business: Business, beliefs: dict[str, dict[str, Any]], decision: Decision, prediction: dict[str, Any],
           actual_effect: float, observed_unit_change: float | None, tags: list[str], uncertainty: float) -> dict[str, Any]:
    """Grade a locked forecast and learn only where attribution is strong enough."""
    plan = prediction["plan"]["profit_delta"]; base_uncertainty = max(0., uncertainty)
    confounder_tags = [t for t in tags if any(w in t.lower() for w in ("festival", "diwali", "ad issue", "suspended", "stockout", "weather", "competitor", "unusual", "holiday", "noise"))]
    effective_uncertainty = base_uncertainty + 0.12 * len(confounder_tags) + (0.04 * max(0, len(tags) - len(confounder_tags)))
    wide = effective_uncertainty > .20 or len(tags) >= 2 or bool(confounder_tags and effective_uncertainty > .18)
    result: dict[str, Any] = {"actual_effect": actual_effect, "uncertainty": effective_uncertainty, "tags": tags, "gradable": not wide, "learned": False, "changes": [], "method": "owner-reviewed seasonal baseline", "reason": None}
    if wide:
        result["reason"] = "The attribution band is too wide after unusual events. The outcome is recorded, but no beliefs changed."
        return result
    result.update(score(plan, actual_effect))
    group = business.group(decision.group)
    # A user-supplied unit change is more defensible than reverse-engineering it from profit alone.
    unit_ratio = (observed_unit_change or 0.) / 100
    changes = []
    if decision.lever == "price":
        if abs(decision.change) < .02 or observed_unit_change is None:
            result["reason"] = "The forecast was graded, but a measured unit change is needed to update price sensitivity."
        else:
            elasticity = math.log(max(1 + unit_ratio, .05)) / math.log(1 + decision.change)
            observation_sd = min(1.8, .45 + effective_uncertainty * 2.5)
            if observation_sd > 1.2: result["reason"] = "The price result is too noisy to learn from."
            else: changes.append(normal_update(beliefs, f"elasticity:{group.key}", elasticity, observation_sd, "reviewed price decision", -4.5, -.02))
    elif decision.lever == "ads":
        if observed_unit_change is None:
            result["reason"] = "The forecast was graded, but a measured unit change is needed to update the ad curve."
        else:
            changes.append(update_ad(beliefs, f"ad:{group.key}", 1 + decision.change, unit_ratio, max(.05, effective_uncertainty), group.ad_share, "reviewed ad decision"))
    elif decision.lever == "promotion":
        if observed_unit_change is None:
            result["reason"] = "The forecast was graded, but a measured unit change is needed to update promotion lift."
        else:
            changes.append(normal_update(beliefs, f"promo_lift:{group.key}", max(0., unit_ratio) / max(decision.change / .1, .1), max(.05, effective_uncertainty), "reviewed promotion", 0., 1.5))
    else:
        result["reason"] = "Restocks are graded for cash and inventory; supplier beliefs update when the delivery is marked complete."
    result["changes"] = changes; result["learned"] = bool(changes)
    return result


def decision_memory_text(decision_id: str, decision: Decision, prediction: dict[str, Any], status: str, actual: dict[str, Any] | None = None) -> str:
    plan = prediction["plan"]["profit_delta"]
    text = (f"Decision {decision_id} {status}. {decision.as_dict()['title']}. "
            f"Predicted profit change ₹{plan['p50']:,.0f}, 80% range ₹{plan['p10']:,.0f} to ₹{plan['p90']:,.0f}. "
            f"Chance of being worse off: {prediction['plan']['loss_chance']:.0%}.")
    if actual:
        text += f" Actual estimated effect ₹{actual.get('actual_effect', 0):,.0f}. "
        text += "Beliefs updated from a clean measurement." if actual.get("learned") else f"No belief change: {actual.get('reason', 'insufficient evidence')}"
    return text
