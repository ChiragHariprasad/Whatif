from __future__ import annotations

import math

from apps.api.whatif.attribution import fit_baseline
from apps.api.whatif.beliefs import initial_beliefs
from apps.api.whatif.config import demo_business
from apps.api.whatif.learning import review
from apps.api.whatif.llm import render_verdict, substitute
from apps.api.whatif.simulator import Decision, simulate


def test_simulation_returns_ordered_ranges_and_cash_fan() -> None:
    business = demo_business()
    output, _ = simulate(business, initial_beliefs(business), Decision("price", "premium", .10), runs=300)
    for scenario in ("nothing", "plan", "test"):
        values = output[scenario]["profit_delta"]
        assert values["p10"] <= values["p50"] <= values["p90"]
        assert len(output[scenario]["cash"]["fan"]["p50"]) == 14
    assert output["nothing"]["profit_delta"]["p50"] == 0


def test_review_updates_clean_price_signal() -> None:
    business = demo_business(); beliefs = initial_beliefs(business)
    prediction, _ = simulate(business, beliefs, Decision("price", "premium", .10), runs=200)
    before = beliefs["elasticity:premium"]["mean"]
    outcome = review(business, beliefs, Decision("price", "premium", .10), prediction, actual_effect=12000, observed_unit_change=-4, tags=[], uncertainty=.08)
    assert outcome["gradable"]
    assert outcome["learned"]
    assert beliefs["elasticity:premium"]["mean"] != before


def test_noisy_review_refuses_to_learn() -> None:
    business = demo_business(); beliefs = initial_beliefs(business)
    prediction, _ = simulate(business, beliefs, Decision("ads", "core", .2), runs=200)
    before = beliefs["ad:core"]["n"]
    outcome = review(business, beliefs, Decision("ads", "core", .2), prediction, actual_effect=0, observed_unit_change=4, tags=["festival", "stockout", "ad issue"], uncertainty=.5)
    assert not outcome["gradable"]
    assert not outcome["learned"]
    assert beliefs["ad:core"]["n"] == before


def test_trend_baseline_falls_back_without_control() -> None:
    baseline = fit_baseline([100, 102, 104, 106, 108], None, None, [1, 1, 1, 1, 1], [1, 1])
    assert baseline is not None
    assert baseline.method == "trend"
    effect, sd = baseline.effect(__import__("numpy").array([111, 114]), [0, 1])
    assert math.isfinite(effect) and sd > 0


def test_guardrail_allows_placeholders_with_digits_but_rejects_literal_numbers() -> None:
    template = "Plan profit is [[profit_p50]], range [[profit_p10]] to [[profit_p90]], loss chance [[loss_chance]]."
    values = {
        "profit_p10": "−₹39,109",
        "profit_p50": "+₹15,000",
        "profit_p90": "+₹45,000",
        "loss_chance": "12%",
    }
    result = substitute(template, values)
    assert result == "Plan profit is +₹15,000, range −₹39,109 to +₹45,000, loss chance 12%."

    # Regression check: Literal digit in generated prose must be rejected
    bad_template = "Plan profit is [[profit_p50]] with a 10 percent probability."
    import pytest
    with pytest.raises(ValueError, match="Generated prose may not contain literal digits"):
        substitute(bad_template, values)


def test_render_verdict_runs_without_raising() -> None:
    business = demo_business()
    sim, _ = simulate(business, initial_beliefs(business), Decision("price", "premium", .10), runs=100)
    verdict = render_verdict(sim)
    assert "text" in verdict and len(verdict["text"]) > 10
    assert "values" in verdict and "profit_p50" in verdict["values"]

