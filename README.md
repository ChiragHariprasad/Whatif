# WHATIF · AI Decision Simulator with Verifiable Memory

> **Ask what if. Decide. Get graded.**  
> WHATIF is a full-stack, twin-based business decision simulator with closed-loop experience memory powered by **Hindsight Cloud**, strict LLM guardrails powered by **Groq**, and autonomous multi-agent validation powered by **Band.ai**.

---

## Table of Contents

- [Overview](#overview)
- [Quick Start from Scratch](#quick-start-from-scratch)
  - [Prerequisites](#prerequisites)
  - [Step 1: Clone the Repository](#step-1-clone-the-repository)
  - [Step 2: Virtual Environment Setup](#step-2-virtual-environment-setup)
  - [Step 3: Environment Variables Configuration](#step-3-environment-variables-configuration)
  - [Step 4: Seed the Three Synthetic Worlds](#step-4-seed-the-three-synthetic-worlds)
  - [Step 5: Start the Application Server](#step-5-start-the-application-server)
  - [Step 6: Run Automated Tests](#step-6-run-automated-tests)
- [Band.ai Tom & Jerry Multi-Agent Pair](#bandai-tom--jerry-multi-agent-pair)
- [The Three Synthetic Business Worlds](#the-three-synthetic-business-worlds)
- [Core Architecture & Boundaries](#core-architecture--boundaries)
- [Documentation Index](#documentation-index)
- [Troubleshooting & FAQ](#troubleshooting--faq)
- [Disclaimer](#disclaimer)

---

## Overview

Running a business requires making decisions under radical uncertainty:
- *Should we raise prices by 10%?*
- *Will doubling ad spend increase margin or just burn cash?*
- *Can we survive restocking 4,000 units given supplier delivery lags?*

Traditional business dashboards look backward; spreadsheet models are fragile; and generic LLMs hallucinate numbers without accountability.

**WHATIF solves this with a three-layer architecture:**
1. **The Vectorized NumPy Twin**: Runs 5,000 Monte Carlo simulations in under 15ms using common random numbers to model 13-week distributions of profit, demand, inventory stockouts, supplier delays, and cash flows.
2. **Hindsight Cloud Memory**: Recalls relevant historical decisions, supplier quote promises, owner notes, and confounders across isolated banks. When reviews arrive, it learns using closed-form Bayesian updates, gating out noisy reviews.
3. **Groq Placeholder Guardrails**: An LLM generates natural-language explanation prose strictly through server-substituted placeholders (`[[profit_p10]]`, `[[profit_p50]]`, `[[loss_chance]]`). Literal digits are strictly rejected by a regex guardrail.

---

## Quick Start from Scratch

Follow these instructions to run WHATIF locally from a fresh clone.

### Prerequisites

- **Python 3.11, 3.12, or 3.13** installed on your system.
- **Git** installed.
- (Optional) **uv** package manager (`pip install uv`) for ultra-fast setup.
- (Optional) **Microsoft Edge** or **Google Chrome** installed if running headless Playwright browser tests.

---

### Step 1: Clone the Repository

```bash
git clone https://github.com/your-username/whatif.git
cd whatif
```

---

### Step 2: Virtual Environment Setup

#### Windows (PowerShell):
```powershell
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Upgrade pip and install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
```

#### macOS / Linux (Bash):
```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

*(Optional) Install Playwright browser drivers if running browser automation tests:*
```bash
playwright install msedge  # or: playwright install chromium
```

---

### Step 3: Environment Variables Configuration

Copy the example `.env` file:

#### Windows:
```powershell
Copy-Item .env.example .env
```

#### macOS / Linux:
```bash
cp .env.example .env
```

Open `.env` in your editor and configure the keys:

```env
# 1. Groq Cloud API Key (for placeholder explanation prose)
# Get your free key at: https://console.groq.com
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b

# 2. Hindsight Cloud API Key (for durable experience memory)
# Documentation & keys at: https://hindsight.vectorize.io
HINDSIGHT_API_KEY=hsk_your_hindsight_api_key_here
HINDSIGHT_BASE_URL=https://api.hindsight.vectorize.io
HINDSIGHT_BANK_ID=whatif-ember-wick

# 3. Band.ai User API Key (for Tom & Jerry agent pair)
# Setup at: https://app.band.ai
BAND_USER_API_KEY=band_u_your_band_api_key_here

# 4. Local Database Default
DATABASE_PATH=whatif.db
```

> [!NOTE]
> **Graceful Fallbacks:** If `HINDSIGHT_API_KEY` is omitted, WHATIF gracefully falls back to local audit SQLite memory and displays `Local demo memory` in the UI. If `GROQ_API_KEY` is omitted, WHATIF uses deterministic template verdicts.

---

### Step 4: Seed the Three Synthetic Worlds

To experience WHATIF with pre-seeded decisions, resolved supplier promises, changing beliefs, and the 18-run scenario library, run the automated seeding script:

#### Windows (PowerShell):
```powershell
$env:PYTHONPATH="."
python data/synthetic/seed_all_worlds.py
```

#### macOS / Linux:
```bash
export PYTHONPATH="."
python data/synthetic/seed_all_worlds.py
```

**What this script does:**
1. Initializes 3 isolated SQLite databases: `whatif.db`, `whatif-northlight-studio.db`, and `whatif-brew-lane-cafe.db`.
2. Connects to 3 isolated Hindsight Cloud banks: `whatif-ember-wick`, `whatif-northlight-studio`, `whatif-brew-lane-cafe`.
3. Simulates and reviews **68 historical decisions** and **107 supplier promises** using real product loop methods.
4. Plants 5 deliberate memory features per bank: distractors, conflicting precedents, evolving beliefs, noisy reviews with confounders, and cold-start partners.
5. Banks the **18 saved run scenarios** (36 runs across Memory On/Off) into `data/synthetic/saved_runs.json`.
6. Executes the 10-seed rehearsal of the live Diwali centerpiece.
7. Executes spot verification queries checking 100% precision and zero cross-bank leakage.

---

### Step 5: Start the Application Server

Start the FastAPI backend with hot-reload enabled:

#### Windows:
```powershell
$env:PYTHONPATH="."
python -m uvicorn apps.api.main:app --port 8000 --reload
```

#### macOS / Linux:
```bash
export PYTHONPATH="."
python -m uvicorn apps.api.main:app --port 8000 --reload
```

The server will start on **`http://127.0.0.1:8000`**.
Open your browser and navigate to:
👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

The web UI loads with zero build steps (pure HTML5, CSS custom properties, and modern ES modules).

---

### Step 6: Run Automated Tests

To run the unit tests and guardrail regression test suite:

```powershell
# Windows
$env:PYTHONPATH="."
pytest -v

# macOS / Linux
export PYTHONPATH="."
pytest -v
```

To run the end-to-end Playwright browser walkthrough:

```powershell
$env:PYTHONPATH="."
python tests/walkthrough_all_worlds.py
```

Screenshots are saved to `scratch/screenshots/`.

---

## Band.ai Tom & Jerry Multi-Agent Pair

WHATIF includes an autonomous multi-agent pair built with **LangGraph** and deployed on **Band.ai**.

- **Tom (Auditor Agent)**: Skeptical financial auditor that interrogates cash flow assumptions and supplier delay probabilities.
- **Jerry (Strategist Agent)**: Optimistic commercial growth strategist that proposes high-upside test configurations.

### Running Tom & Jerry:

```powershell
cd band/tom-jerry-agents

# Install dependencies via uv
uv sync

# In Terminal 1: Run Tom
uv run python tom_agent.py

# In Terminal 2: Run Jerry
uv run python jerry_agent.py
```

Open [https://app.band.ai](https://app.band.ai), start a chat, invite **Tom**, and prompt:
`@Tom review our Diwali restock cash cliff with @Jerry`.

---

## The Three Synthetic Business Worlds

You can switch between three completely independent business worlds directly via the dropdown in the UI topbar:

| Business World | Domain | Monthly Revenue | Gross Margin | Reality Partner | Hindsight Bank |
|---|---|---|---|---|---|
| **Ember & Wick Candle Co.** (Hero) | D2C Candle Brand | ₹15,00,000 | 58% | Rajan Jars & Speedy Courier | `whatif-ember-wick` |
| **Northlight Studio** | Design & Dev Agency | ₹45,00,000 | 55% | Net-30 Clients & Contractors | `whatif-northlight-studio` |
| **Brew Lane Café** | Single-Outlet F&B | ₹28,00,000 | 52% | Fresh Produce & Delivery App | `whatif-brew-lane-cafe` |

---

## Core Architecture & Boundaries

```text
┌────────────────────────────────────────────────────────┐
│               Web Browser (Single Page App)            │
│           Vanilla JS · Semantic CSS · SVG Fans         │
└──────────────────────────┬─────────────────────────────┘
                           │ REST / JSON API (:8000)
┌──────────────────────────▼─────────────────────────────┐
│                   FastAPI Application                  │
├──────────────────────────┬─────────────────────────────┤
│   NumPy Vector Twin      │  5,000-run Monte Carlo      │
│   (Math & Cashflows)     │  Common random numbers      │
├──────────────────────────┼─────────────────────────────┤
│   Bayesian Learner       │  Conjugate updates          │
│   (Closed-Form Updates)  │  Confounder gating          │
├──────────────────────────┼─────────────────────────────┤
│   Hindsight Memory       │  Cloud Bank: retain/recall  │
│   (Experience Memory)    │  Local SQLite audit backup  │
├──────────────────────────┼─────────────────────────────┤
│   Groq LLM Guardrail     │  Placeholder substitution   │
│   (Natural Prose)        │  Regex digit enforcement    │
└────────────────────────────────────────────────────────┘
```

---

## Documentation Index

For in-depth guides, explore the `docs/` directory:

1. **[UI Navigation & Demo Guide](docs/UI_GUIDE.md)**: Screen-by-screen breakdown of all 5 UI pages, how to run simulations, commit forecasts, tag confounders, and 2-min/4-min presentation scripts.
2. **[Architecture & Technical Deep Dive](docs/architecture.md)**: Mathematical formulations, twin demand equations, Bayesian equations, memory ontology, and Band multi-agent protocols.
3. **[Codebase Audit & Improvements](docs/CODEBASE_AUDIT_AND_IMPROVEMENTS.md)**: Comprehensive audit detailing hardcoded values, logic edge cases, parser constraints, and roadmap recommendations.
4. **[Demo Testing & Browser Walkthrough Report](docs/DEMO_TESTING_AND_WALKTHROUGH_REPORT.md)**: Empirical test report containing the 10-seed rehearsal table, 18 saved runs, and 18 high-res screenshots.

---

## Troubleshooting & FAQ

### 1. `ModuleNotFoundError: No module named 'apps'`
**Cause**: Python cannot find the root package when running tests or scripts.  
**Fix**: Ensure `PYTHONPATH` is set to the current directory:
- PowerShell: `$env:PYTHONPATH="."`
- Bash: `export PYTHONPATH="."`

### 2. `405 Method Not Allowed` when switching worlds
**Cause**: Uvicorn server was running on an outdated code cache.  
**Fix**: Start uvicorn with the `--reload` flag (`python -m uvicorn apps.api.main:app --port 8000 --reload`). The endpoint `/api/worlds/switch` supports `GET`, `POST`, and `PUT`.

### 3. Hindsight Memory status shows `Local demo memory`
**Cause**: `HINDSIGHT_API_KEY` is missing or invalid in your `.env`.  
**Fix**: Verify your key in `.env`. Ensure there are no surrounding quotes or trailing spaces.

### 4. Port 8000 already in use
**Cause**: Another instance of uvicorn is running in the background.  
**Fix**:
- Windows: `Get-Process python | Stop-Process` or find PID with `netstat -ano | findstr :8000` and kill it.
- Linux/macOS: `lsof -ti :8000 | xargs kill -9`

---

## Disclaimer

WHATIF is a decision simulation and planning aid using synthetic business data and closed-form mathematical modeling. It is **not** financial, tax, investment, or legal advice.
