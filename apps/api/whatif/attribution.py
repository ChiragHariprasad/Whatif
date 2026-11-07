"""Attribution without pretending every business decision is a controlled experiment."""
from __future__ import annotations

import math
from dataclasses import dataclass
import numpy as np

MIN_PRE_WEEKS, MAX_PRE_WEEKS, SD_LOG_FLOOR = 4, 12, .03


@dataclass
class Baseline:
    method: str
    counterfactual: np.ndarray
    residual_sd: float
    n_pre: int
    inflate: float = 1.
    note: str = ""

    def effect(self, actual: np.ndarray, indexes: list[int], widen: float = 1.) -> tuple[float, float]:
        if not indexes: return 0., float("inf")
        residual = np.log(np.maximum(actual[indexes], 1e-9) / np.maximum(self.counterfactual[indexes], 1e-9))
        return float(residual.mean()), self.residual_sd * math.sqrt(1 / self.n_pre + 1 / len(indexes)) * self.inflate * widen


def fit_baseline(treated_pre: np.ndarray, comparison_pre: np.ndarray | None, comparison_post: np.ndarray | None, seasonal_pre: np.ndarray, seasonal_post: np.ndarray) -> Baseline | None:
    n = min(len(treated_pre), MAX_PRE_WEEKS)
    if n < MIN_PRE_WEEKS: return None
    treated = np.maximum(np.asarray(treated_pre[-n:], float), 1e-9)
    if comparison_pre is not None and comparison_post is not None and len(comparison_pre) >= n:
        ratio = np.log(treated / np.maximum(np.asarray(comparison_pre[-n:], float), 1e-9))
        return Baseline("did-log", np.asarray(comparison_post, float) * math.exp(float(ratio.mean())), max(float(ratio.std(ddof=1)), SD_LOG_FLOOR), n, note="Compared with an untouched product group.")
    deseasoned = np.log(treated) - np.log(np.asarray(seasonal_pre[-n:], float)); time = np.arange(-n + 1, 1, dtype=float)
    slope, intercept = np.polyfit(time, deseasoned, 1); residual = deseasoned - (intercept + slope * time)
    s = max(float(residual.std(ddof=2)) if n > 2 else SD_LOG_FLOOR, SD_LOG_FLOOR); future = np.arange(1, len(seasonal_post) + 1, dtype=float)
    sxx = max(float(((time - time.mean()) ** 2).sum()), 1e-9); inflate = math.sqrt(1 + float(((future.mean() - time.mean()) ** 2) / sxx)) * 1.3
    return Baseline("trend", np.exp(intercept + slope * future) * np.asarray(seasonal_post, float), s, n, inflate, "Seasonal-trend baseline; no untouched comparison group was available.")


def score(prediction: dict[str, float], actual: float) -> dict[str, float | bool]:
    pinball = sum(max(tau * (actual - prediction[key]), (tau - 1) * (actual - prediction[key])) for tau, key in ((.1, "p10"), (.5, "p50"), (.9, "p90"))) / 3
    return {"error": abs(actual - prediction["p50"]), "covered": prediction["p10"] <= actual <= prediction["p90"], "pinball": pinball}


def recalibration_scale(records: list[dict[str, float]]) -> float:
    if len(records) < 15: return 1.
    ratios = [abs(item["actual"] - item["p50"]) / max((item["p90"] - item["p10"]) / 2, 1e-6) for item in records]
    return float(np.clip(np.quantile(ratios, .8), .6, 3.))
