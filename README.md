# WHATIF — ask what if. Decide. Get graded.

WHATIF is a full-stack decision simulator for a product business. It simulates 13 weeks of revenue, inventory, delayed cash receipts and supplier lead-time risk; locks a prediction when a decision is committed; then grades and learns from the outcome.

The demo defaults to **Lumen & Wick Candle Co.**, a synthetic candle business. It deliberately runs with local deterministic fallbacks, so a polished demo does not depend on a network call. Configure Hindsight to activate durable experience memory.

## Run it

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn apps.api.main:app --reload --port 8000
```

Open http://127.0.0.1:8000. The FastAPI server serves the mobile-first web app and API together.

Run tests with:

```powershell
python -m pytest -q
```

## Hindsight is a first-class part of the product

Set `HINDSIGHT_API_KEY` and optionally `HINDSIGHT_BANK_ID` in `.env`. The API will lazily create one bank per business with a skeptical/literal decision-memory mission. It uses:

1. **retain** when a decision is committed, reviewed, a promise is added, or a promise is delivered;
2. **recall** while simulating with Memory On, returning the cited precedents in the result Evidence panel;
3. **reflect** for the “why were we off?” answer and weekly brief; and
4. an explicit Memory Off path that skips recall and uses only generic priors.

The numeric beliefs, locked forecasts and audit trail remain in the local database. Hindsight stores the experience and narrative evidence, never silently overwriting the model's numbers.

The integration is graceful: if the key is absent or Hindsight is temporarily unavailable, the UI says `Local demo memory` and preserves the full loop locally. That makes it safe to demo offline while retaining the actual production integration.

## Architecture

```text
web UI (HTML/CSS/JS) ── REST/JSON ── FastAPI
                                         ├── vectorised NumPy business twin
                                         ├── attribution + scoring + belief updates
                                         ├── SQLite (or a replaceable persistence adapter)
                                         ├── Hindsight Cloud: retain / recall / reflect
                                         └── optional Groq explanation client
```

`apps/api/whatif/simulator.py` contains the financial calculations; `learning.py` is where reviews affect beliefs; `memory.py` is the only Hindsight boundary. This separation is intentional: generated prose cannot alter money calculations.

## Band Tom & Jerry pair

`band/tom-jerry-agents/` is a standalone Band project scaffolded for the LangGraph adapter and Groq's OpenAI-compatible endpoint. Agent credentials are intentionally ignored by git. See [band/tom-jerry-agents/README.md](band/tom-jerry-agents/README.md) for the startup commands.

## Limitations

This is a planning aid, not financial, tax, legal, or investment advice. The demo business and its outcomes are synthetic. A review can correctly refuse to update a belief if the attribution band is too wide.
