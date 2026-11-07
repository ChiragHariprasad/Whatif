from apps.api.whatif.beliefs import initial_beliefs
from apps.api.whatif.config import brew_lane_cafe_business, northlight_studio_business
from apps.api.whatif.learning import review
from apps.api.whatif.llm import money
from apps.api.whatif.simulator import Decision, parse_question, simulate, test_decision as smaller_test


def test_agency_revenues_are_delayed_and_use_domain_seasonality() -> None:
    business = northlight_studio_business()
    result, run = simulate(business, initial_beliefs(business), Decision("price", "retainers", 0), runs=300)
    assert business.receipt_delay_share == 1
    assert business.seasonal[43] == 1.0
    assert result["plan"]["cash"]["fan"]["p50"][1] < business.cash0
    assert run["receipts"][:, 0].mean() < run["revenue"][:, 0].mean() * .1


def test_low_volume_restock_test_is_not_forced_to_250_units() -> None:
    business = northlight_studio_business()
    decision = Decision("price", "retainers", .05, linked_decisions=[Decision("restock", "projects", 2)])
    test = smaller_test(decision, business)
    assert test.linked_decisions[0].change == 1


def test_compound_parser_uses_the_active_business_and_user_values() -> None:
    business = northlight_studio_business()
    decision = parse_question("Diwali: raise Retainer rates 5%, spend 30% more on ads, restock 2 projects", business)
    assert decision.group == "retainers"
    assert decision.change == .05
    assert {(item.lever, item.group, item.change) for item in decision.linked_decisions} == {("ads", "retainers", .3), ("restock", "projects", 2.0)}


def test_horizon_confounds_and_currency_are_configurable() -> None:
    business = brew_lane_cafe_business()
    result, _ = simulate(business, initial_beliefs(business), Decision("price", "dine_in", .05), runs=100, horizon=26)
    assert result["horizon"] == 26
    assert len(result["plan"]["cash"]["fan"]["p50"]) == 27
    beliefs = initial_beliefs(business)
    outcome = review(business, beliefs, Decision("price", "dine_in", .05), result, 0, 1, [], .01, major_confounder=True)
    assert not outcome["learned"] and not outcome["gradable"]
    assert money(1234567, "$", "en-US") == "+$1,234,567"


def test_world_header_isolation_and_batch_delivery_endpoint(tmp_path, monkeypatch) -> None:
    from fastapi.testclient import TestClient
    import apps.api.main as api

    api._stores.clear(); api._memories.clear()
    for world in api.WORLDS.values():
        monkeypatch.setitem(world, "db", str(tmp_path / f"{world['id']}.db"))
    with TestClient(api.app) as client:
        north = client.get("/api/business", headers={"X-World-ID": "northlight-studio"}).json()["business"]
        cafe = client.get("/api/business", headers={"X-World-ID": "brew-lane-cafe"}).json()["business"]
        assert north["name"] == "Northlight Studio" and north["delayed_receipts_share"] == 1
        assert cafe["name"] == "Brew Lane Café"
        result = client.post("/api/simulate", headers={"X-World-ID": "northlight-studio"}, json={"question": "Raise Retainer rates 5%", "memory_on": False, "horizon": 26})
        assert result.status_code == 200 and result.json()["horizon"] == 26
        promise = client.post("/api/promises", headers={"X-World-ID": "brew-lane-cafe"}, json={"message": "FreshFarms order will arrive in 2 days."}).json()["promise"]
        batch = client.post("/api/promises/batch-deliver", headers={"X-World-ID": "brew-lane-cafe"}, json={"deliveries": [{"id": promise["id"], "actual_days": 3}]})
        assert batch.status_code == 200 and batch.json()["promises"][0]["delivered_days"] == 3
