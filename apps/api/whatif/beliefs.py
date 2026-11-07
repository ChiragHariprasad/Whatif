from __future__ import annotations

import copy
import math
from typing import Any

import numpy as np

from .config import Business

ELASTICITY_PRIOR = (-1.8, .8)
PROMO_LIFT_PRIOR = (.35, .20)
PROMO_PULL_PRIOR = (.12, .12)
PARTNER_PRIORS = {"supplier": (1.10, .18, 3), "courier": (1.15, .20, 3), "other": (1.08, .18, 3)}
H_GRID = np.array([.8, 1.0, 1.3, 1.7, 2.2])
K_GRID = np.exp(np.linspace(math.log(.15), math.log(8), 28))


def hill(spend: np.ndarray | float, shape: np.ndarray | float, half_sat: np.ndarray | float) -> np.ndarray:
    spend = np.maximum(spend, 1e-9)
    return spend ** shape / (spend ** shape + half_sat ** shape)


def initial_beliefs(business: Business) -> dict[str, dict[str, Any]]:
    beliefs: dict[str, dict[str, Any]] = {}
    weights = np.exp(-.5 * ((np.log(K_GRID) - math.log(1.6)) / .9) ** 2)
    weights = np.outer(np.ones(len(H_GRID)), weights); weights /= weights.sum()
    for group in business.groups:
        beliefs[f"elasticity:{group.key}"] = {"kind": "elasticity", "mean": -1.8, "sd": .8, "n": 0, "source": "prior", "history": []}
        beliefs[f"ad:{group.key}"] = {"kind": "ad", "mean": float((weights.sum(0) * K_GRID).sum()), "sd": 1.0, "n": 0, "source": "prior", "weights": weights.ravel().tolist(), "history": []}
        beliefs[f"promo_lift:{group.key}"] = {"kind": "promo_lift", "mean": .35, "sd": .20, "n": 0, "source": "prior", "history": []}
        beliefs[f"promo_pull:{group.key}"] = {"kind": "promo_pull", "mean": .12, "sd": .12, "n": 0, "source": "prior", "history": []}
    for partner in business.partners:
        ratio, sigma, pseudo_n = PARTNER_PRIORS.get(partner.type, PARTNER_PRIORS["other"])
        beliefs[f"partner:{partner.key}"] = {"kind": "partner", "mean": math.log(ratio), "sd": sigma / math.sqrt(pseudo_n), "n": 0, "source": "prior", "sigma": sigma, "hedge_delta": 0., "type": partner.type, "observations": [], "history": []}
    return beliefs


def clone_for_memory_off(business: Business) -> dict[str, dict[str, Any]]:
    return initial_beliefs(business)


def normal_update(beliefs: dict[str, dict[str, Any]], key: str, observed: float, observed_sd: float,
                  event: str, lower: float | None = None, upper: float | None = None) -> dict[str, Any]:
    belief = beliefs[key]; before = copy.deepcopy(belief)
    precision = 1 / max(belief["sd"], .01) ** 2
    observation_precision = 1 / max(observed_sd, .01) ** 2
    belief["mean"] = (precision * belief["mean"] + observation_precision * observed) / (precision + observation_precision)
    belief["sd"] = max(math.sqrt(1 / (precision + observation_precision)), .03)
    if lower is not None: belief["mean"] = max(lower, belief["mean"])
    if upper is not None: belief["mean"] = min(upper, belief["mean"])
    belief["n"] += 1; belief["source"] = "learned"
    belief["history"].append({"event": event, "before": before["mean"], "after": belief["mean"]})
    return {"name": key, "before": before, "after": copy.deepcopy(belief)}


def update_ad(beliefs: dict[str, dict[str, Any]], key: str, spend_ratio: float, observed_ratio: float,
              observed_sd: float, ad_share: float, event: str) -> dict[str, Any]:
    belief = beliefs[key]; before = copy.deepcopy(belief)
    weights = np.asarray(belief["weights"]).reshape(len(H_GRID), len(K_GRID))
    shapes, halves = np.meshgrid(H_GRID, K_GRID, indexing="ij")
    predicted = ad_share * (hill(spend_ratio, shapes, halves) / hill(1, shapes, halves) - 1)
    weights *= np.exp(-.5 * ((observed_ratio - predicted) / max(observed_sd, .01)) ** 2) + 1e-12
    weights /= weights.sum()
    half_weights = weights.sum(axis=0); mean = float((half_weights * K_GRID).sum())
    belief.update(weights=weights.ravel().tolist(), mean=mean, sd=float(np.sqrt((half_weights * (K_GRID - mean) ** 2).sum())), n=belief["n"] + 1, source="learned")
    belief["history"].append({"event": event, "before": before["mean"], "after": mean})
    return {"name": key, "before": before, "after": copy.deepcopy(belief)}


def update_partner(beliefs: dict[str, dict[str, Any]], key: str, promised: float, actual: float, hedged: bool, event: str) -> dict[str, Any]:
    belief = beliefs[key]; before = copy.deepcopy(belief)
    obs = list(belief.get("observations", [])) + [[math.log(max(actual, .5) / max(promised, .5)), int(hedged)]]
    xs = np.asarray([x[0] for x in obs]); hs = np.asarray([x[1] for x in obs])
    hedge_delta = float(xs[hs == 1].mean() - xs[hs == 0].mean()) * hs.sum() / (hs.sum() + 2) if hs.sum() and (~hs.astype(bool)).sum() else 0.
    ratio, prior_sigma, pseudo_n = PARTNER_PRIORS.get(belief["type"], PARTNER_PRIORS["other"])
    adjusted = xs - hedge_delta * hs
    mean = (pseudo_n * math.log(ratio) + adjusted.sum()) / (pseudo_n + len(xs))
    sigma = max(math.sqrt((pseudo_n * prior_sigma ** 2 + ((adjusted - mean) ** 2).sum()) / (pseudo_n + len(xs))), .04)
    belief.update(mean=float(mean), sd=float(sigma / math.sqrt(pseudo_n + len(xs))), sigma=float(sigma), hedge_delta=float(hedge_delta), observations=obs, n=len(obs), source="learned")
    belief["history"].append({"event": event, "before": before["mean"], "after": belief["mean"]})
    return {"name": key, "before": before, "after": copy.deepcopy(belief)}


def summary(business: Business, beliefs: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for name, belief in beliefs.items():
        kind, target = name.split(":", 1)
        if kind == "elasticity":
            group = business.group(target); sentence = f"{group.name} buyers {'barely react' if belief['mean'] > -.8 else 'react strongly'} to price."
        elif kind == "ad":
            group = business.group(target); sentence = f"{group.name} ad returns reach saturation around {belief['mean']:.1f}× spend."
        elif kind == "promo_lift": sentence = f"A 10% {business.group(target).name} promotion lifts units about {belief['mean'] * 100:.0f}%."
        elif kind == "promo_pull": sentence = f"About {belief['mean'] * 100:.0f}% of {business.group(target).name} promotion sales pull forward."
        else:
            partner = business.partner(target); extra = math.exp(belief.get('hedge_delta', 0)) - 1
            sentence = f"{partner.name} says {partner.promised_days:.0f} days, delivers about {partner.promised_days * math.exp(belief['mean']):.0f}."
            if abs(extra) > .03: sentence += f" Hedged promises add about {extra * partner.promised_days:.0f} days."
        result.append({"name": name, "kind": kind, "label": target.replace("-", " ").title(), "sentence": sentence, **belief})
    return result
