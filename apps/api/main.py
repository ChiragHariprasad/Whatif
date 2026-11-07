from __future__ import annotations

import os
import re
import uuid
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .whatif.attribution import recalibration_scale
from .whatif.beliefs import clone_for_memory_off, summary, update_partner
from .whatif.config import LEVERS
from .whatif.learning import decision_memory_text, review
from .whatif.llm import groq_placeholders, render_verdict, substitute
from .whatif.memory import HindsightMemory
from .whatif.simulator import Decision, parse_question, simulate, title_for
from .whatif.storage import Store, utcnow

load_dotenv()
store = Store(); store.initialize(); memory = HindsightMemory(store)
app = FastAPI(title="WHATIF API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class ParseRequest(BaseModel): question: str = Field(min_length=3, max_length=1000)

class DecisionInput(BaseModel):
    lever: str
    group: str
    change: float
    start: int = Field(default=1, ge=0, le=12)
    duration: int = Field(default=4, ge=1, le=13)
    title: str | None = None

    def domain(self) -> Decision:
        if self.lever not in LEVERS: raise HTTPException(422, "Choose price, ads, promotion, or restock.")
        return Decision(**self.model_dump())

class SimulateRequest(BaseModel):
    question: str | None = None
    decision: DecisionInput | None = None
    memory_on: bool = True
    now_week: int | None = Field(default=None, ge=0, le=51)

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

class PromiseRequest(BaseModel):
    message: str = Field(min_length=3, max_length=3000)
    partner_key: str | None = None
    item: str | None = None
    promised_days: float | None = Field(default=None, gt=0, le=365)

class DeliverRequest(BaseModel): actual_days: float = Field(gt=0, le=365)
class BusinessUpdate(BaseModel): monthly_revenue: float | None = Field(default=None, gt=0); gross_margin: float | None = Field(default=None, gt=0, lt=1); cash: float | None = Field(default=None, ge=0); monthly_fixed: float | None = Field(default=None, ge=0); monthly_ads: float | None = Field(default=None, ge=0)


def calibration() -> float:
    scorecard = store.scorecard(); records = [{key: item[key] for key in ("actual", "p10", "p50", "p90")} for item in scorecard["records"]]
    return recalibration_scale(records)


def current_decision(request: SimulateRequest) -> Decision:
    if request.decision: return request.decision.domain()
    if request.question: return parse_question(request.question, store.business())
    raise HTTPException(422, "Provide a question or an editable decision card.")


@app.get("/api/health")
def health() -> dict[str, Any]: return {"ok": True, "memory": memory.status(), "database": str(store.path)}

@app.get("/api/business")
def get_business() -> dict[str, Any]:
    business = store.business(); return {"business": business.to_dict(), "headline": {"monthly_revenue": business.monthly_revenue, "gross_margin": business.gross_margin, "cash": business.cash0, "monthly_fixed": business.monthly_fixed, "monthly_ads": business.monthly_ad_spend}}

@app.put("/api/business")
def update_business(payload: BusinessUpdate) -> dict[str, Any]:
    business = store.business(); business.rescale(payload.monthly_revenue, payload.gross_margin, payload.cash, payload.monthly_fixed, payload.monthly_ads); store.set_business(business)
    return get_business()

@app.post("/api/parse-question")
def parse(payload: ParseRequest) -> dict[str, Any]:
    decision = parse_question(payload.question, store.business()); return {"decision": decision.as_dict(), "parser": "deterministic"}

@app.post("/api/simulate")
async def simulate_endpoint(payload: SimulateRequest) -> dict[str, Any]:
    business = store.business(); decision = current_decision(payload); week = payload.now_week if payload.now_week is not None else store.week()
    beliefs = store.beliefs() if payload.memory_on else clone_for_memory_off(business)
    response, _ = simulate(business, beliefs, decision, now_week=week, calibration_scale=calibration())
    recalled = memory.recall(f"{decision.lever} decision for {decision.group}: {title_for(decision)}", ["decision", f"lever:{decision.lever}", f"group:{decision.group}"], payload.memory_on)
    verdict = render_verdict(response)
    # Groq receives only the already-computed values, never authority to calculate.
    generated = await groq_placeholders({"decision": response["decision"], "allowed_placeholders": list(verdict["values"])})
    if generated:
        try: verdict["text"] = substitute(generated, verdict["values"]); verdict["template"] = generated; verdict["guardrail"] = "placeholder-substitution"
        except ValueError: pass
    response.update(memory={**recalled, "mode": "Memory On" if payload.memory_on else "Memory Off", "status": memory.status()}, verdict=verdict,
                    evidence_note="Precedents explain assumptions and flag confounders; only reviewed numeric beliefs change simulation inputs.",
                    test_rule={"success": "Central profit estimate stays positive and the actual result lands within the stated range.", "stop": "Stop if cash falls below the p10 minimum or stockout risk exceeds 25%."})
    return response

@app.post("/api/decisions/commit")
def commit(payload: CommitRequest) -> dict[str, Any]:
    decision = payload.decision.domain(); prediction = payload.prediction
    if "plan" not in prediction or "profit_delta" not in prediction["plan"]: raise HTTPException(422, "Commit the exact simulation response, including plan ranges.")
    decision_id = f"D-{uuid.uuid4().hex[:8].upper()}"; review_date = payload.review_date or (date.today() + timedelta(days=max(7, decision.duration * 7))).isoformat()
    item = {"id": decision_id, "title": title_for(decision), "payload": {**decision.as_dict(), "hypothesis": payload.hypothesis or f"{title_for(decision)} improves profit without a harmful cash dip.", "success_rule": payload.success_rule or "Actual result is inside the stated 80% range."}, "prediction": prediction, "memory_on": payload.memory_on, "status": "committed", "created_at": utcnow(), "review_date": review_date}
    store.add_decision(item)
    memory.retain("decision", decision_id, decision_memory_text(decision_id, decision, prediction, "committed"), ["decision", f"lever:{decision.lever}", f"group:{decision.group}", "status:committed"], item["created_at"])
    return {"decision": store.get_decision(decision_id), "message": "Prediction locked. WHATIF will grade this against the outcome on the review date."}

@app.get("/api/decisions")
def decisions(status: str | None = None) -> dict[str, Any]:
    data = store.list_decisions(); return {"items": [item for item in data if not status or item["status"] == status]}

@app.get("/api/decisions/{decision_id}")
def decision_detail(decision_id: str) -> dict[str, Any]:
    item = store.get_decision(decision_id)
    if not item: raise HTTPException(404, "Decision not found")
    return item

@app.post("/api/decisions/{decision_id}/review")
def review_endpoint(decision_id: str, payload: ReviewRequest) -> dict[str, Any]:
    item = store.get_decision(decision_id)
    if not item: raise HTTPException(404, "Decision not found")
    if item["status"] == "reviewed": raise HTTPException(409, "This decision has already been reviewed.")
    business = store.business(); beliefs = store.beliefs(); decision = Decision(**{key: item["payload"][key] for key in ("lever", "group", "change", "start", "duration", "title")})
    outcome = review(business, beliefs, decision, item["prediction"], payload.actual_effect, payload.observed_unit_change, payload.tags, payload.uncertainty)
    outcome["note"] = payload.note
    if outcome["learned"]: store.set_beliefs(beliefs)
    store.review_decision(decision_id, outcome)
    memory.retain("review", decision_id, decision_memory_text(decision_id, decision, item["prediction"], "reviewed", outcome), ["decision", f"lever:{decision.lever}", f"group:{decision.group}", "status:reviewed"], utcnow())
    return {"decision": store.get_decision(decision_id), "learning": outcome, "scorecard": store.scorecard()}

@app.get("/api/beliefs")
def beliefs() -> dict[str, Any]: return {"items": summary(store.business(), store.beliefs()), "memory": memory.status()}

@app.post("/api/beliefs/{name}/forget")
def forget_belief(name: str) -> dict[str, Any]:
    beliefs = store.beliefs(); fresh = clone_for_memory_off(store.business())
    if name not in beliefs: raise HTTPException(404, "Belief not found")
    history = beliefs[name].get("history", []); beliefs[name] = fresh[name]; beliefs[name]["history"] = history + [{"event": "Forgotten by owner"}]; store.set_beliefs(beliefs)
    return {"items": summary(store.business(), beliefs)}

@app.get("/api/scorecard")
def scorecard() -> dict[str, Any]:
    card = store.scorecard(); card["calibration_scale"] = calibration(); card["range_message"] = f"{card['gradable_reviews']} graded reviews — show counts until six reviews, not a percentage." if card["gradable_reviews"] < 6 else "Observed coverage is compared with the stated 80% range."
    return card

@app.get("/api/partners")
def partners() -> dict[str, Any]:
    business = store.business(); beliefs = store.beliefs(); promises = store.list_promises(); output = []
    for partner in business.partners:
        belief = beliefs[f"partner:{partner.key}"]; ratio = __import__("math").exp(belief["mean"]); related = [p for p in promises if p["partner_key"] == partner.key]
        output.append({"key": partner.key, "name": partner.name, "type": partner.type, "promised_days": partner.promised_days, "expected_days": partner.promised_days * ratio, "observations": belief["n"], "reliability": "Learning" if belief["n"] < 3 else ("At risk" if ratio > 1.25 else "Reliable"), "promises": related})
    return {"items": output}

def promise_preview(message: str, preferred: str | None = None) -> dict[str, Any]:
    business = store.business(); lower = message.lower(); partners = business.partners
    partner = next((p for p in partners if p.key == preferred), None) if preferred else next((p for p in partners if p.name.lower().split()[0] in lower or p.key.split("-")[0] in lower), partners[0])
    match = re.search(r"(?:in|within|by)\s*(\d+)\s*(?:business\s*)?(?:day|days)", lower); days = float(match.group(1)) if match else partner.promised_days
    hedge = any(word in lower for word in ("should", "hopefully", "try", "likely", "maybe", "expect"))
    return {"partner_key": partner.key, "partner_name": partner.name, "item": "supplier delivery", "quote": message, "promised_days": days, "hedged": hedge}

@app.post("/api/promises")
def add_promise(payload: PromiseRequest) -> dict[str, Any]:
    preview = promise_preview(payload.message, payload.partner_key); preview["item"] = payload.item or preview["item"]; preview["promised_days"] = payload.promised_days or preview["promised_days"]
    promise_id = f"P-{uuid.uuid4().hex[:8].upper()}"; item = {"id": promise_id, **preview, "created_at": utcnow()}; store.add_promise(item)
    memory.retain("promise", promise_id, f"Promise {promise_id}: {preview['partner_name']} promised {preview['item']} in {preview['promised_days']:.0f} days. Quote: {preview['quote']}", ["promise", f"partner:{preview['partner_key']}", "hedged" if preview["hedged"] else "firm"], item["created_at"])
    return {"promise": item, "preview": preview}

@app.post("/api/promises/{promise_id}/deliver")
def deliver(promise_id: str, payload: DeliverRequest) -> dict[str, Any]:
    item = store.get_promise(promise_id)
    if not item: raise HTTPException(404, "Promise not found")
    if item["delivered_days"] is not None: raise HTTPException(409, "This promise is already marked delivered.")
    store.deliver_promise(promise_id, payload.actual_days); business = store.business(); beliefs = store.beliefs()
    change = update_partner(beliefs, f"partner:{item['partner_key']}", item["promised_days"], payload.actual_days, item["hedged"], "resolved promise"); store.set_beliefs(beliefs)
    memory.retain("promise", promise_id, f"Promise {promise_id} resolved. {business.partner(item['partner_key']).name} promised {item['promised_days']:.0f} days and delivered in {payload.actual_days:.0f} days. Hedged: {item['hedged']}.", ["promise", f"partner:{item['partner_key']}", "status:resolved"], utcnow())
    return {"promise": store.get_promise(promise_id), "belief_change": change}

@app.post("/api/reflect")
def reflect(question: str = "Why were my last forecasts off?") -> dict[str, Any]: return memory.reflect(question, ["decision", "status:reviewed"])

@app.post("/api/demo/advance")
def demo_advance(step: int = 1) -> dict[str, Any]:
    store.set_week(store.week() + step); return {"week": store.week(), "message": "Demo time machine advanced. Simulations now use the new calendar week."}

@app.get("/api/demo/ground-truth")
def demo_ground_truth() -> dict[str, Any]:
    """Explicit reveal only; the simulator and learner never import this file."""
    source = Path(__file__).resolve().parents[2] / "data" / "synthetic" / "ground_truth.json"
    if not source.exists(): raise HTTPException(404, "Generate synthetic demo data first.")
    return json.loads(source.read_text(encoding="utf-8"))

@app.get("/api/home")
def home() -> dict[str, Any]:
    business = store.business(); decision = Decision("price", "premium", 0, start=1, duration=1); outlook, _ = simulate(business, store.beliefs(), decision, now_week=store.week(), runs=1000, calibration_scale=calibration())
    return {"business": business.name, "week": store.week(), "cash": outlook["plan"]["cash"], "scorecard": store.scorecard(), "memory": memory.status(), "due": [item for item in store.list_decisions() if item["status"] == "committed"][:3]}


web_path = Path(__file__).parent.parent / "web"
app.mount("/", StaticFiles(directory=web_path, html=True), name="web")
