from __future__ import annotations

import os
import re
import uuid
import json
from contextvars import ContextVar
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .whatif.attribution import recalibration_scale
from .whatif.beliefs import clone_for_memory_off, summary, update_partner, initial_beliefs
from .whatif.config import (
    LEVERS,
    ember_wick_business,
    northlight_studio_business,
    brew_lane_cafe_business,
)
from .whatif.learning import decision_memory_text, review
from .whatif.llm import groq_placeholders, render_verdict, substitute
from .whatif.memory import HindsightMemory
from .whatif.simulator import Decision, parse_question, simulate, title_for
from .whatif.storage import Store, utcnow

load_dotenv(override=True)

WORLDS = {
    "ember-wick": {
        "id": "ember-wick", "name": "Ember & Wick Candle Co.", "category": "D2C Brand",
        "db": "whatif.db", "bank_id": "whatif-ember-wick", "business_fn": ember_wick_business
    },
    "northlight-studio": {
        "id": "northlight-studio", "name": "Northlight Studio", "category": "Agency",
        "db": "whatif-northlight-studio.db", "bank_id": "whatif-northlight-studio", "business_fn": northlight_studio_business
    },
    "brew-lane-cafe": {
        "id": "brew-lane-cafe", "name": "Brew Lane Café", "category": "Café",
        "db": "whatif-brew-lane-cafe.db", "bank_id": "whatif-brew-lane-cafe", "business_fn": brew_lane_cafe_business
    },
}
DEFAULT_WORLD_ID = "ember-wick"
_request_world_id: ContextVar[str] = ContextVar("request_world_id", default=DEFAULT_WORLD_ID)
_stores: dict[str, Store] = {}
_memories: dict[str, HindsightMemory] = {}


def current_world_id() -> str:
    return _request_world_id.get()


def get_store(world_id: str | None = None) -> Store:
    wid = world_id or current_world_id()
    if wid not in _stores:
        cfg = WORLDS.get(wid, WORLDS["ember-wick"])
        st = Store(cfg["db"])
        st.initialize()
        with st.lock, st.connection() as db:
            row = db.execute("SELECT value FROM settings WHERE key='business'").fetchone()
            if not row:
                b = cfg["business_fn"]()
                st.set_business(b)
                st.put_setting("beliefs", initial_beliefs(b))
                st.put_setting("week", 18 if wid == "ember-wick" else 12)
            else:
                # Persisted demo databases predate receipt timing, locale, and
                # domain-seasonality fields. Apply only that safe config upgrade.
                raw = json.loads(row["value"])
                if "delayed_receipts_share" not in raw:
                    defaults = cfg["business_fn"]()
                    business = st.business()
                    business.delayed_receipts_share = defaults.delayed_receipts_share
                    business.currency_symbol = defaults.currency_symbol
                    business.locale = defaults.locale
                    business.seasonal = defaults.seasonal
                    st.set_business(business)
        _stores[wid] = st
    return _stores[wid]


def get_memory(world_id: str | None = None) -> HindsightMemory:
    wid = world_id or current_world_id()
    if wid not in _memories:
        cfg = WORLDS.get(wid, WORLDS["ember-wick"])
        _memories[wid] = HindsightMemory(get_store(wid), bank_id=cfg["bank_id"], bank_name=f"WHATIF · {cfg['name']}")
    return _memories[wid]


app = FastAPI(title="WHATIF API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def select_request_world(request: Request, call_next: Any) -> Any:
    requested = request.headers.get("X-World-ID") or request.cookies.get("whatif_world") or DEFAULT_WORLD_ID
    token = _request_world_id.set(requested if requested in WORLDS else DEFAULT_WORLD_ID)
    try:
        return await call_next(request)
    finally:
        _request_world_id.reset(token)


class ParseRequest(BaseModel): question: str = Field(min_length=3, max_length=1000)

class DecisionInput(BaseModel):
    lever: str
    group: str
    change: float
    start: int = Field(default=1, ge=0, le=51)
    duration: int = Field(default=4, ge=1, le=52)
    title: str | None = None

    def domain(self) -> Decision:
        if self.lever not in LEVERS: raise HTTPException(422, "Choose price, ads, promotion, or restock.")
        return Decision(**self.model_dump())

class SimulateRequest(BaseModel):
    question: str | None = None
    decision: DecisionInput | None = None
    memory_on: bool = True
    now_week: int | None = Field(default=None, ge=0, le=51)
    horizon: int = Field(default=13, ge=13, le=52)

class CommitRequest(BaseModel):
    decision: DecisionInput
    prediction: dict[str, Any]
    memory_on: bool = True
    hypothesis: str | None = None
    success_rule: str | None = None
    review_date: str | None = None

class ReviewRequest(BaseModel):
    actual_effect: float
    observed_unit_change: float | None = Field(default=None, ge=-95, le=1000)
    uncertainty: float = Field(default=.10, ge=0, le=2)
    tags: list[str] = Field(default_factory=list, max_length=8)
    note: str | None = Field(default=None, max_length=1000)
    major_confounder: bool = False

class PromiseRequest(BaseModel):
    message: str = Field(min_length=3, max_length=3000)
    partner_key: str | None = None
    item: str | None = None
    promised_days: float | None = Field(default=None, gt=0, le=365)

class DeliverRequest(BaseModel): actual_days: float = Field(gt=0, le=365)
class BatchDeliverItem(BaseModel): id: str = Field(min_length=3); actual_days: float = Field(gt=0, le=365)
class BatchDeliverRequest(BaseModel): deliveries: list[BatchDeliverItem] = Field(min_length=1, max_length=100)
class BusinessUpdate(BaseModel): monthly_revenue: float | None = Field(default=None, gt=0); gross_margin: float | None = Field(default=None, gt=0, lt=1); cash: float | None = Field(default=None, ge=0); monthly_fixed: float | None = Field(default=None, ge=0); monthly_ads: float | None = Field(default=None, ge=0)


def calibration() -> float:
    store = get_store()
    scorecard = store.scorecard(); records = [{key: item[key] for key in ("actual", "p10", "p50", "p90")} for item in scorecard["records"]]
    return recalibration_scale(records)


def current_decision(request: SimulateRequest) -> Decision:
    store = get_store()
    if request.decision: return request.decision.domain()
    if request.question: return parse_question(request.question, store.business())
    raise HTTPException(422, "Provide a question or an editable decision card.")


@app.get("/api/worlds")
def list_worlds() -> dict[str, Any]:
    return {
        "active": current_world_id(),
        "worlds": [
            {"id": w["id"], "name": w["name"], "category": w["category"], "bank_id": w["bank_id"], "active": w["id"] == current_world_id()}
            for w in WORLDS.values()
        ]
    }


@app.api_route("/api/worlds/switch", methods=["GET", "POST", "PUT"])
@app.api_route("/api/worlds/switch/{world_id}", methods=["GET", "POST", "PUT"])
@app.api_route("/api/worlds/{world_id}/switch", methods=["GET", "POST", "PUT"])
async def switch_world(request: Request, world_id: str | None = None) -> dict[str, Any]:
    target = world_id
    if not target:
        target = request.query_params.get("world_id") or request.query_params.get("world")
    if not target:
        try:
            body = await request.json()
            if isinstance(body, dict):
                target = body.get("world_id") or body.get("world") or body.get("id")
        except Exception:
            pass
    if not target:
        raise HTTPException(422, "Please provide world_id (e.g. ember-wick, northlight-studio, brew-lane-cafe).")

    target_clean = str(target).lower().strip()
    if target_clean in WORLDS:
        chosen = target_clean
    elif "agency" in target_clean or "northlight" in target_clean:
        chosen = "northlight-studio"
    elif "cafe" in target_clean or "brew" in target_clean:
        chosen = "brew-lane-cafe"
    elif "ember" in target_clean or "candle" in target_clean or "wick" in target_clean:
        chosen = "ember-wick"
    else:
        raise HTTPException(404, f"World '{target}' not found. Choose ember-wick, northlight-studio, or brew-lane-cafe.")

    st = get_store(chosen)
    mem = get_memory(chosen)
    response = JSONResponse({
        "ok": True,
        "active": chosen,
        "world_id": chosen,
        "business": st.business().name,
        "bank_id": mem.bank_id,
    })
    response.set_cookie("whatif_world", chosen, httponly=False, samesite="lax")
    return response


@app.get("/api/health")
def health() -> dict[str, Any]:
    store = get_store(); memory = get_memory()
    return {"ok": True, "active_world": current_world_id(), "business": store.business().name, "memory": memory.status(), "database": str(store.path)}


@app.get("/api/business")
def get_business() -> dict[str, Any]:
    store = get_store()
    business = store.business(); return {"business": business.to_dict(), "headline": {"monthly_revenue": business.monthly_revenue, "gross_margin": business.gross_margin, "cash": business.cash0, "monthly_fixed": business.monthly_fixed, "monthly_ads": business.monthly_ad_spend}}


@app.api_route("/api/business", methods=["PUT", "POST"])
def update_business(payload: BusinessUpdate) -> dict[str, Any]:
    store = get_store()
    business = store.business(); business.rescale(payload.monthly_revenue, payload.gross_margin, payload.cash, payload.monthly_fixed, payload.monthly_ads); store.set_business(business)
    return get_business()


@app.post("/api/parse-question")
def parse(payload: ParseRequest) -> dict[str, Any]:
    store = get_store()
    decision = parse_question(payload.question, store.business()); return {"decision": decision.as_dict(), "parser": "deterministic"}


@app.post("/api/simulate")
async def simulate_endpoint(payload: SimulateRequest) -> dict[str, Any]:
    store = get_store(); memory = get_memory()
    business = store.business(); decision = current_decision(payload); week = payload.now_week if payload.now_week is not None else store.week()
    beliefs = store.beliefs() if payload.memory_on else clone_for_memory_off(business)
    response, _ = simulate(business, beliefs, decision, now_week=week, calibration_scale=calibration(), horizon=payload.horizon)
    recalled = await memory.arecall(f"{decision.lever} decision for {decision.group}: {title_for(decision)}", ["decision", f"lever:{decision.lever}", f"group:{decision.group}"], payload.memory_on)
    verdict = render_verdict(response, business.currency_symbol, business.locale)
    generated = await groq_placeholders({"decision": response["decision"], "allowed_placeholders": list(verdict["values"])})
    if generated:
        try: verdict["text"] = substitute(generated, verdict["values"]); verdict["template"] = generated; verdict["guardrail"] = "placeholder-substitution"
        except ValueError: pass
    response.update(memory={**recalled, "mode": "Memory On" if payload.memory_on else "Memory Off", "status": memory.status()}, verdict=verdict,
                    evidence_note="Precedents explain assumptions and flag confounders; only reviewed numeric beliefs change simulation inputs.",
                    test_rule={"success": "Central profit estimate stays positive and the actual result lands within the stated range.", "stop": "Stop if cash falls below the p10 minimum or stockout risk exceeds 25%."})
    return response


@app.post("/api/decisions/commit")
async def commit(payload: CommitRequest) -> dict[str, Any]:
    store = get_store(); memory = get_memory()
    decision = payload.decision.domain(); prediction = payload.prediction
    if "plan" not in prediction or "profit_delta" not in prediction["plan"]: raise HTTPException(422, "Commit the exact simulation response, including plan ranges.")
    decision_id = f"D-{uuid.uuid4().hex[:8].upper()}"; review_date = payload.review_date or (date.today() + timedelta(days=max(7, decision.duration * 7))).isoformat()
    p_plan = prediction.get("plan", {})
    clear_bet = p_plan.get("profit_delta", {}).get("p50", 0) > 0 and p_plan.get("loss_chance", 1) < 0.45
    default_hypothesis = f"{title_for(decision)} improves profit without a harmful cash dip." if clear_bet else f"Test whether {title_for(decision)} avoids a harmful cash dip despite uncertain return."
    item = {"id": decision_id, "title": title_for(decision), "payload": {**decision.as_dict(), "hypothesis": payload.hypothesis or default_hypothesis, "success_rule": payload.success_rule or "Actual result is inside the stated 80% range."}, "prediction": prediction, "memory_on": payload.memory_on, "status": "committed", "created_at": utcnow(), "review_date": review_date}
    store.add_decision(item)
    await memory.aretain("decision", decision_id, decision_memory_text(decision_id, decision, prediction, "committed"), ["decision", f"lever:{decision.lever}", f"group:{decision.group}", "status:committed"], item["created_at"])
    return {"decision": store.get_decision(decision_id), "message": "Prediction locked. WHATIF will grade this against the outcome on the review date."}


@app.get("/api/decisions")
def decisions(status: str | None = None) -> dict[str, Any]:
    store = get_store()
    data = store.list_decisions(); return {"items": [item for item in data if not status or item["status"] == status]}


@app.get("/api/decisions/{decision_id}")
def decision_detail(decision_id: str) -> dict[str, Any]:
    store = get_store()
    item = store.get_decision(decision_id)
    if not item: raise HTTPException(404, "Decision not found")
    return item


@app.post("/api/decisions/{decision_id}/review")
async def review_endpoint(decision_id: str, payload: ReviewRequest) -> dict[str, Any]:
    store = get_store(); memory = get_memory()
    item = store.get_decision(decision_id)
    if not item: raise HTTPException(404, "Decision not found")
    if item["status"] == "reviewed": raise HTTPException(409, "This decision has already been reviewed.")
    business = store.business(); beliefs = store.beliefs(); decision = Decision(**{key: item["payload"][key] for key in ("lever", "group", "change", "start", "duration", "title")})
    outcome = review(business, beliefs, decision, item["prediction"], payload.actual_effect, payload.observed_unit_change, payload.tags, payload.uncertainty, payload.major_confounder)
    outcome["note"] = payload.note
    if outcome["learned"]: store.set_beliefs(beliefs)
    store.review_decision(decision_id, outcome)
    await memory.aretain("review", decision_id, decision_memory_text(decision_id, decision, item["prediction"], "reviewed", outcome), ["decision", f"lever:{decision.lever}", f"group:{decision.group}", "status:reviewed"], utcnow())
    return {"decision": store.get_decision(decision_id), "learning": outcome, "scorecard": store.scorecard()}


@app.get("/api/beliefs")
def beliefs() -> dict[str, Any]:
    store = get_store(); memory = get_memory()
    return {"items": summary(store.business(), store.beliefs()), "memory": memory.status()}


@app.post("/api/beliefs/{name}/forget")
def forget_belief(name: str) -> dict[str, Any]:
    store = get_store()
    beliefs = store.beliefs(); fresh = clone_for_memory_off(store.business())
    if name not in beliefs: raise HTTPException(404, "Belief not found")
    history = beliefs[name].get("history", []); beliefs[name] = fresh[name]; beliefs[name]["history"] = history + [{"event": "Forgotten by owner"}]; store.set_beliefs(beliefs)
    return {"items": summary(store.business(), beliefs)}


@app.get("/api/scorecard")
def scorecard() -> dict[str, Any]:
    store = get_store()
    card = store.scorecard(); card["calibration_scale"] = calibration(); card["range_message"] = f"{card['gradable_reviews']} graded reviews — show counts until six reviews, not a percentage." if card["gradable_reviews"] < 6 else "Observed coverage is compared with the stated 80% range."
    return card


@app.get("/api/partners")
def partners() -> dict[str, Any]:
    store = get_store()
    business = store.business(); beliefs = store.beliefs(); promises = store.list_promises(); output = []
    for partner in business.partners:
        belief = beliefs[f"partner:{partner.key}"]; ratio = __import__("math").exp(belief["mean"]); related = [p for p in promises if p["partner_key"] == partner.key]
        output.append({"key": partner.key, "name": partner.name, "type": partner.type, "promised_days": partner.promised_days, "expected_days": partner.promised_days * ratio, "observations": belief["n"], "reliability": "Learning" if belief["n"] < 3 else ("At risk" if ratio > 1.25 else "Reliable"), "promises": related})
    return {"items": output}


def promise_preview(message: str, preferred: str | None = None) -> dict[str, Any]:
    store = get_store()
    business = store.business(); lower = message.lower(); partners = business.partners
    partner = next((p for p in partners if p.key == preferred), None) if preferred else next((p for p in partners if p.name.lower().split()[0] in lower or p.key.split("-")[0] in lower), partners[0])
    match = re.search(r"(?:in|within|by)\s*(\d+)\s*(?:business\s*)?(?:day|days)", lower); days = float(match.group(1)) if match else partner.promised_days
    hedge = any(word in lower for word in ("should", "hopefully", "try", "likely", "maybe", "expect"))
    return {"partner_key": partner.key, "partner_name": partner.name, "item": "supplier delivery", "quote": message, "promised_days": days, "hedged": hedge}


@app.post("/api/promises")
async def add_promise(payload: PromiseRequest) -> dict[str, Any]:
    store = get_store(); memory = get_memory()
    preview = promise_preview(payload.message, payload.partner_key); preview["item"] = payload.item or preview["item"]; preview["promised_days"] = payload.promised_days or preview["promised_days"]
    promise_id = f"P-{uuid.uuid4().hex[:8].upper()}"; item = {"id": promise_id, **preview, "created_at": utcnow()}; store.add_promise(item)
    await memory.aretain("promise", promise_id, f"Promise {promise_id}: {preview['partner_name']} promised {preview['item']} in {preview['promised_days']:.0f} days. Quote: {preview['quote']}", ["promise", f"partner:{preview['partner_key']}", "hedged" if preview["hedged"] else "firm"], item["created_at"])
    return {"promise": item, "preview": preview}


@app.post("/api/promises/{promise_id}/deliver")
async def deliver(promise_id: str, payload: DeliverRequest) -> dict[str, Any]:
    store = get_store(); memory = get_memory()
    item = store.get_promise(promise_id)
    if not item: raise HTTPException(404, "Promise not found")
    if item["delivered_days"] is not None: raise HTTPException(409, "This promise is already marked delivered.")
    store.deliver_promise(promise_id, payload.actual_days); business = store.business(); beliefs = store.beliefs()
    change = update_partner(beliefs, f"partner:{item['partner_key']}", item["promised_days"], payload.actual_days, item["hedged"], "resolved promise"); store.set_beliefs(beliefs)
    await memory.aretain("promise", promise_id, f"Promise {promise_id} resolved. {business.partner(item['partner_key']).name} promised {item['promised_days']:.0f} days and delivered in {payload.actual_days:.0f} days. Hedged: {item['hedged']}.", ["promise", f"partner:{item['partner_key']}", "status:resolved"], utcnow())
    return {"promise": store.get_promise(promise_id), "belief_change": change}


@app.post("/api/promises/batch-deliver")
async def deliver_batch(payload: BatchDeliverRequest) -> dict[str, Any]:
    store = get_store(); memory = get_memory()
    if len({item.id for item in payload.deliveries}) != len(payload.deliveries):
        raise HTTPException(422, "Each promise may appear only once.")
    promises = []
    for delivery in payload.deliveries:
        item = store.get_promise(delivery.id)
        if not item: raise HTTPException(404, f"Promise {delivery.id} not found")
        if item["delivered_days"] is not None: raise HTTPException(409, f"Promise {delivery.id} is already marked delivered.")
        promises.append((item, delivery.actual_days))
    store.deliver_promises([(item["id"], days) for item, days in promises])
    beliefs = store.beliefs(); changes = []
    for item, days in promises:
        changes.append(update_partner(beliefs, f"partner:{item['partner_key']}", item["promised_days"], days, item["hedged"], "batch-resolved promise"))
        await memory.aretain("promise", item["id"], f"Promise {item['id']} resolved in a batch. {item['partner_name']} promised {item['promised_days']:.0f} days and delivered in {days:.0f} days.", ["promise", f"partner:{item['partner_key']}", "status:resolved"], utcnow())
    store.set_beliefs(beliefs)
    return {"promises": [store.get_promise(item["id"]) for item, _ in promises], "belief_changes": changes}


@app.post("/api/reflect")
async def reflect(question: str = "Why were my last forecasts off?") -> dict[str, Any]:
    memory = get_memory()
    return await memory.areflect(question, ["decision", "status:reviewed"])


@app.post("/api/demo/advance")
def demo_advance(step: int = 1) -> dict[str, Any]:
    store = get_store()
    store.set_week(store.week() + step); return {"week": store.week(), "message": "Demo time machine advanced. Simulations now use the new calendar week."}


@app.get("/api/demo/ground-truth")
def demo_ground_truth() -> dict[str, Any]:
    source = Path(__file__).resolve().parents[2] / "data" / "synthetic" / f"ground_truth_{current_world_id()}.json"
    if not source.exists():
        source = Path(__file__).resolve().parents[2] / "data" / "synthetic" / "ground_truth.json"
    if not source.exists(): raise HTTPException(404, "Generate synthetic demo data first.")
    return json.loads(source.read_text(encoding="utf-8"))


@app.get("/api/home")
def home() -> dict[str, Any]:
    store = get_store(); memory = get_memory()
    business = store.business(); first_group = business.groups[0].key
    decision = Decision("price", first_group, 0, start=1, duration=1)
    outlook, _ = simulate(business, store.beliefs(), decision, now_week=store.week(), runs=1000, calibration_scale=calibration())
    return {"business": business.name, "world_id": current_world_id(), "week": store.week(), "cash": outlook["plan"]["cash"], "scorecard": store.scorecard(), "memory": memory.status(), "due": [item for item in store.list_decisions() if item["status"] == "committed"][:3]}


web_path = Path(__file__).parent.parent / "web"
app.mount("/", StaticFiles(directory=web_path, html=True), name="web")
