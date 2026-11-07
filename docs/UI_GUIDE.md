# WHATIF · User Interface & Navigation Guide

This manual is written for presenters, video creators, teammates, and operators. It explains how to navigate, operate, and present every screen of **WHATIF** without needing to read the underlying Python or JavaScript source code.

---

## Table of Contents

1. [Global Navigation & Topbar](#1-global-navigation--topbar)
2. [Page 1: Overview (Cash Outlook & Attention Feed)](#2-page-1-overview-cash-outlook--attention-feed)
3. [Page 2: Ask What If (Decision Composer & 5,000-Run Simulation)](#3-page-2-ask-what-if-decision-composer--5000-run-simulation)
4. [Page 3: Decisions (The Prediction Ledger & Review Process)](#4-page-3-decisions-the-prediction-ledger--review-process)
5. [Page 4: Reality Layer (Partners, Quotes & Delays)](#5-page-4-reality-layer-partners-quotes--delays)
6. [Page 5: Learn (Scorecard, Calibration & Beliefs)](#6-page-5-learn-scorecard-calibration--beliefs)
7. [The Live Centerpiece: The Diwali Compound Scenario](#7-the-live-centerpiece-the-diwali-compound-scenario)
8. [Recommended Video Recording Scripts](#8-recommended-video-recording-scripts)
   - [4-Minute Full Walkthrough Cut](#4-minute-full-walkthrough-cut)
   - [2-Minute High-Impact Pitch Cut](#2-minute-high-impact-pitch-cut)

---

## 1. Global Navigation & Topbar

The persistent navigation chrome surrounds the main workspace on desktop and mobile.

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  [W] WHATIF      [Eyebrow: Business Name]                     [World: Dropdown ▼]      │
│  · Overview      A clearer next move.                         [Hindsight · Memory On]  │
│  · Decisions                                                  [Avatar: Settings]       │
│  · Reality Layer                                                                       │
│  · Learn                                                                               │
│                                                                                        │
│  [Demo week 18]                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key Elements:
* **Brand & Sidebar Rail (Desktop)**:
  * `Overview (⌂)`: Business dashboard, cash fan chart, and pending tasks.
  * `Decisions (◫)`: Immutable prediction ledger and review interfaces.
  * `Reality layer (↗)`: Partner profiles, lead times, quote capture, and actual delivery resolution.
  * `Learn (◌)`: Calibration scorecard, Bayesian beliefs, and reflection.
* **World Selector Dropdown (`#worldSelect`)**:
  * Located in the top-right header actions.
  * Allows switching between three independent synthetic business worlds:
    1. **Ember & Wick Candle Co.** (D2C E-commerce hero brand)
    2. **Northlight Studio** (Design & software agency)
    3. **Brew Lane Café** (Single-outlet food & beverage)
  * Selecting a world immediately hot-swaps the underlying SQLite database and Hindsight memory bank in-place without losing your current page view.
* **Memory Status Pill (`#memoryStatus`)**:
  * Displays `Hindsight · memory on` when connected to live Hindsight Cloud.
  * Displays `Local demo memory` if running offline with local SQLite audit fallback.
* **Demo Week Pill (`#advanceDemo`)**:
  * Displays `Demo week X` at the bottom of the sidebar.
  * Clicking it advances the synthetic business calendar by +1 week, allowing you to simulate time passing and advance seasonal demand.
* **Floating Action Button (`+ Ask what if`)**:
  * Fixed at bottom-right; clicking it from any page instantly opens the Decision Composer.

---

## 2. Page 1: Overview (Cash Outlook & Attention Feed)

The Overview page answers: *"Where does our business stand today, and what demands our attention?"*

```text
┌───────────────────────────────────────┬────────────────────────────────────────┐
│  ASK A DECISION QUESTION              │  CASH OUTLOOK · NEXT 13 WEEKS          │
│  What are you thinking of changing?   │  Likely lowest point: ₹2,12,135 in Wk 1│
│  [ e.g. Raise Premium prices 10%... ] │  [~~~~ 80% Monte Carlo Shaded Band ~~~]│
│  [See range →]                        │  [━━━━ Central p50 Likely Cash Path ━━]│
│  Chips: [Raise prices] [Spend on ads] │                                        │
└───────────────────────────────────────┴────────────────────────────────────────┘
```

### 1. The 13-Week Cash Outlook Fan Chart:
* **The Green Line (`p50`)**: The median simulated cash balance over the next 13 weeks across 5,000 common-random Monte Carlo simulations.
* **The Shaded Corridor (`p10` to `p90`)**: The 80% credible range representing real business uncertainty (delayed customer receipts, courier delays, demand fluctuations).
* **Likely Lowest Point Metric**: The minimum central cash balance and the exact week it occurs. If the lowest point dips below zero, the metric highlights in warning red (`warn`).

### 2. Quick Ask Bar & Chips:
* Type any natural language business change, e.g.:
  * *"Raise Premium prices 10% for four weeks"*
  * *"Spend 20% more on ads"*
  * *"Run a 10% Core promotion"*
  * *"Restock 250 Premium units"*
* Or click any of the preset chip buttons to load a pre-formulated question into the composer.

### 3. "Needs Your Attention" Section:
Three cards summarize operational priorities:
1. **Decisions Waiting for Review**: Forecasts whose review date has passed, ready to be graded against reality.
2. **Reality is a Model Input**: Prompt to log recent supplier or courier delivery promises.
3. **Forecast Scorecard**: Shows the total number of graded forecasts and the range coverage reliability percentage (or count for $<6$ reviews).

---

## 3. Page 2: Ask What If (Decision Composer & 5,000-Run Simulation)

This is the core predictive engine where decisions are formulated, simulated, and audited against experience.

### Step 1: Decision Composer & Memory Toggle
* Enter the proposed change in plain English.
* **Memory Mode Toggle**:
  * **Memory On**: Queries Hindsight Cloud for past precedent decisions, supplier reliability, and owner confounder notes. Uses updated Bayesian beliefs.
  * **Memory Off**: Skips memory retrieval entirely; runs Monte Carlo simulations using generic, uncalibrated starting priors without narrative precedents.
* Click **Make decision card →** to parse the natural language query into deterministic levers.

### Step 2: The Editable Decision Card
The deterministic parser maps the text into 5 standard business levers:
* **Lever**: `Price`, `Ads`, `Promotion`, or `Restock`.
* **Product Group**: The target collection (e.g., `Premium`, `Core`, `Gifting` for candles; `Retainers`, `Projects` for agency; `Dine-in`, `Delivery` for café).
* **Change**: Magnitude of change (+10% price, -20% ads, 500 units restock).
* **Starts Week**: Calendar week offset inside the 13-week horizon (e.g., Week 1).
* **Duration**: How many weeks the change remains active (e.g., 4 weeks).
* *Note: All fields are fully editable by the user before running simulations.*

### Step 3: Run 5,000 Simulations
Clicking **Run 5,000 simulations →** sends the decision to the vectorized NumPy twin. Within **15 milliseconds**, the twin runs 5,000 parallel paths and renders the **Scenario Comparison Grid**:

```text
┌────────────────────────┬────────────────────────┬────────────────────────┐
│  SCENARIO: DO NOTHING  │  SCENARIO: YOUR PLAN   │  RECOMMENDED: TEST 1ST │
│  ₹0                    │  −₹4,747               │  −₹1,029               │
│  [====== Range ======] │  [=== p10 to p90 ===]  │  [=== Tighter Range =] │
│  Range: ₹0 — ₹0        │  Range: −₹39k — +₹32k  │  Range: −₹13k — +₹11k  │
│  0% chance worse off   │  57% chance worse off  │  54% chance worse off  │
│  Low cash: ₹2,11,993   │  Low cash: ₹2,11,993   │  Low cash: ₹2,11,993   │
└────────────────────────┴────────────────────────┴────────────────────────┘
```

1. **Do Nothing (Baseline)**: Incremental profit delta is ₹0 by definition; shows baseline cash runway.
2. **Your Plan**: The proposed decision. Shows central profit delta (`p50`), 80% credible range (`p10` to `p90`), chance of being worse off, and minimum cash point.
3. **Test First (The Safe Alternative)**: A smaller, split, or capped version automatically generated by the twin (e.g., testing +5% for 2 weeks instead of +10% for 4 weeks; or splitting a 4,000-unit restock into 1,000-unit batches).
4. **The "Recommended" Badge**: Assigned automatically by deterministic decision rules (not an LLM guess): the full plan is recommended only when central profit is positive and downside risk does not exceed the test.

### Step 4: "Why We Think This" Evidence Drawer
Expand the drawer to audit the foundations of the forecast:
* **Evidence (Hindsight Cloud)**: Direct citations of historical decisions, past review outcomes, and owner confounder notes retrieved from memory.
* **Three Assumptions That Matter**: Displays the 3 critical model parameters driving the result (e.g., Price Elasticity, Supplier Delivery Days, Cash on Delivery Share) alongside their observation count (`"Learned from 8 reviews"` vs `"Starting assumption"`).

### Step 5: Committing to the Plan
* Click **Commit this plan** or **Commit test**.
* The **Commit Modal** opens with:
  * **Hypothesis**: Pre-filled dynamically based on whether the plan is a clear bet or a risk-mitigation test.
  * **Success Rule**: Explicit criteria for grading (e.g., *"Actual result falls inside the stated 80% range"*).
  * **Review Date**: Scheduled automatically based on start week and duration.
* Click **Lock prediction** to write the immutable forecast into the Decisions ledger.

---

## 4. Page 3: Decisions (The Prediction Ledger & Review Process)

The Decisions page enforces honesty: every forecast is locked upfront, and every outcome is recorded with its receipts.

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  PREDICTION LEDGER · Locked against the outcome.                                       │
│  Decision                        Prediction             Review Date  Status   Action   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  Raise Premium prices 10%        +₹34,009               2025-11-15   REVIEWED Details →│
│  Diwali Campaign Restock         −₹42,395               2025-11-20   COMMITTED Review →│
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Reviewing a Committed Decision:
When a decision is due for review, click **Review →**. The modal requests real-world observations:
1. **Actual Profit Change (₹)**: Measured financial impact compared to seasonal baseline.
2. **Observed Unit Change (%)**: Measured percentage change in unit volume.
3. **Attribution Uncertainty Slider**: Baseline uncertainty (default 0.10).
4. **Unusual Events / Confounder Tags**: Comma-separated tags describing external events that distorted the result (e.g., `festival`, `diwali rush`, `ad tracking glitch`, `competitor stockout`, `monsoon flood`).
5. **Owner Note**: Qualitative narrative explanation of what happened.

### How the System Responds to Reviews:
* **Clean Review (No major confounders)**:
  * The outcome is graded against the locked 80% range (inside or outside).
  * The Bayesian learner updates the closed-form elasticity or ad saturation belief.
  * The update is retained in Hindsight Cloud.
* **Confounded / Noisy Review (`effective_uncertainty > 0.20`)**:
  * The system recognizes that external noise contaminated the data.
  * Output: `"The attribution band is too wide after unusual events. The outcome is recorded, but no beliefs changed."`
  * Prevents over-reacting or learning the wrong lesson from a chaotic week!

---

## 5. Page 4: Reality Layer (Partners, Quotes & Delays)

Businesses do not fail from poor ideas; they fail from partner delays causing stockouts and cash crunches.

```text
┌───────────────────────────────────────┬────────────────────────────────────────┐
│  CAPTURE A PROMISE                    │  WHY THIS CHANGES SIMULATION           │
│  Paste the actual message:            │  Promises become cash timing.          │
│  [ Rajan: jars should be ready in 10  │  A late supplier causes stockouts.     │
│    days, hopefully Friday.          ] │  A slow courier delays cash arrival.   │
│  [Add promise]                        │  WHATIF narrows reality with each one. │
└───────────────────────────────────────┴────────────────────────────────────────┘
```

### Capturing a Promise:
1. Paste an unstructured chat message, email snippet, or WhatsApp text into the box.
2. The natural language extractor parses:
   * **Partner Identity**: Matches partner name from business directory.
   * **Promised Lead Time**: Extracts days (e.g., `10 days`).
   * **Hedge Detection**: Identifies hedge phrases (`"should be"`, `"hopefully"`, `"expect"`, `"trying to"`), which trigger an automatic 2–3 day uncertainty expansion.
3. Click **Add promise** to retain the quote in memory and log it under the partner.

### Resolving a Promise:
When the shipment or payment actually arrives:
1. Click **Mark delivered →** on the active promise.
2. Enter the **Actual Delivery Days** (e.g., `16 days`).
3. The Bayesian partner updater revises the partner's log-normal delay ratio:
   * **Rajan Jars**: Promises 10 days, delivers median 16 days $\rightarrow$ Partner tagged as `"At risk"`.
   * **Speedy Courier**: Promises 7 days, remits cash in 12 days $\rightarrow$ Slows down future cash receipt timing in Monte Carlo simulations.

---

## 6. Page 5: Learn (Scorecard, Calibration & Beliefs)

The Learn page provides a radical audit of whether the decision twin's predictions actually match real-world outcomes.

### Tab 1: The Scorecard
* **Forecasts Graded**: Total number of clean, gradable reviewed decisions.
* **Median Error**: Median absolute rupee discrepancy between `p50` forecast and attributed outcome.
* **Range Reliability**: Percentage of actual outcomes that landed inside the locked 80% range:
  * **Integrity Rule**: Displays exact counts (e.g., `4 of 5`) when $< 6$ reviews exist, and percentages (e.g., `81.5%`) once $\ge 6$ reviews exist.
  * **Target Nominal Benchmark**: 80% (well-calibrated forecasts capture 8 out of 10 outcomes).
* **Calibration Log Table**: Complete audit history showing each decision, predicted central value, actual outcome, and whether the 80% range held.
* **"Why were we off?" Button (`#askWhy`)**:
  * Calls Hindsight Cloud's `reflect` API.
  * Synthesizes cross-decision reasoning citing past confounders, stockouts, and partner delays without hallucinating numbers.
* **"Reveal synthetic truth" Button (`#revealTruth`)**:
  * Opens the secret ground-truth parameters modal for post-presentation verification.

### Tab 2: Beliefs
* Displays all active Bayesian distributions:
  * Premium & Core Price Elasticity
  * Ad Saturation Curvature
  * Promotion Lift & Pull-Forward Cannibalization
  * Partner Lead Time Delay Ratios
* Visual progress bars show certainty narrowing as reviews accumulate (`"Learned from 12 reviews"`).
* **"Forget" Button**: Lets the business owner reset a single belief back to its generic uncalibrated prior if market conditions fundamentally shift.

---

## 7. The Live Centerpiece: The Diwali Compound Scenario

For live demonstrations and video recordings, use the **Diwali Compound Scenario** on Ember & Wick Candle Co. It exercises all layers of the system simultaneously.

### The Question:
> *"Diwali Campaign: Core price +8%, Ads +2L, restock 4,000 jars from Rajan Jars"*

### The Dramatic Narrative Beats:
1. **The Compound Levers**: Combines 3 interacting levers (+8% core price, +45% ads spend, 4,000 units restock from Rajan Jars).
2. **The Outlay Hazard**: Ordering 4,000 jars upfront costs ₹24,00,000. With starting cash at ₹1,20,000, the Monte Carlo cash path plunges to **−₹23.49 Lakhs in Week 2** with a **100% negative cash probability**!
3. **The Conflicting Precedents**:
   * Hindsight recalls a failed Core price hike in normal Week 22 (-₹14,500).
   * Hindsight also recalls a successful Core price hike in festival Week 43 (+₹28,200), but flags that it was confounded by festival rush.
4. **The Safe Alternative**: The system rejects the full plan and recommends **Test First: split restock to 1,000 jars (Batch 1) and cap ad increases**, lifting minimum cash by ₹18.9 Lakhs and preventing insolvency.

---

## 8. Recommended Video Recording Scripts

### 4-Minute Full Walkthrough Cut

* **[0:00 – 0:30] Introduction & Problem Setup**
  * *Visual*: Home Overview showing Ember & Wick Candle Co., 13-week cash fan chart, week 18.
  * *Script*: *"Most business decision tools either look backward through stale dashboards or use LLMs that hallucinate financial numbers. WHATIF is different: it’s an AI decision twin where deterministic math owns the money, Hindsight Cloud owns the memory, and every forecast earns an immutable receipt."*
* **[0:30 – 1:15] Ask What If & Memory On vs Off**
  * *Visual*: Type Diwali scenario into Ask composer. Toggle Memory Off, then Memory On.
  * *Script*: *"Let’s test a high-stakes Diwali campaign: raising Core prices 8%, boosting Instagram ads by ₹2 Lakhs, and ordering 4,000 jars from our supplier Rajan Jars. Notice what happens when Memory is Off: the model has no context. But toggle Memory On, and Hindsight Cloud instantly recalls past supplier lead times and conflicting festival precedents."*
* **[1:15 – 2:00] Simulation & The Cash Cliff**
  * *Visual*: Click 'Run 5,000 simulations'. Point to Scenario Grid and 'Why we think this' drawer.
  * *Script*: *"In 15 milliseconds, 5,000 Monte Carlo runs analyze our cash flow. Look at the warning: ordering 4,000 jars upfront creates a catastrophic cash cliff of minus ₹23.5 Lakhs in Week 2 with 100% risk of insolvency. Instead of letting us crash, WHATIF recommends 'Test First'—split the order into 1,000-jar batches and cap ad spend, keeping our runway alive."*
* **[2:00 – 2:45] Commit & Confounder Review**
  * *Visual*: Click 'Commit test'. Navigate to Decisions ledger. Open Review modal.
  * *Script*: *"We lock our forecast into the Decisions ledger. When review day arrives, we enter our actual outcome. But suppose an unusual monsoon storm disrupted delivery. We tag 'monsoon, weather'. Watch what the Bayesian learner does: because external noise was too high, it records the result but refuses to corrupt our underlying beliefs. It learns only from clean signals."*
* **[2:45 – 3:30] Reality Layer & Partner Promises**
  * *Visual*: Navigate to Reality Layer. Paste Rajan Jars message, click 'Add promise', then 'Mark delivered'.
  * *Script*: *"Suppliers don't operate on spreadsheets. In our Reality Layer, we paste raw WhatsApp messages. WHATIF extracts the promise and detects hedge words like 'should be'. When deliveries arrive late, the partner distribution updates, directly shifting future cash delay assumptions."*
* **[3:30 – 4:00] Multi-World Isolation & Scorecard**
  * *Visual*: Switch dropdown to Northlight Studio, then Brew Lane Café. Open Learn tab and show 81.5% range coverage.
  * *Script*: *"Finally, memory is strictly isolated. Switching to our Agency or Café worlds mounts independent databases and separate Hindsight banks with zero cross-contamination. Over 27 graded reviews, our range reliability hits 81.5% against our stated 80% target. Honest forecasting, verified with receipts."*

---

### 2-Minute High-Impact Pitch Cut

* **[0:00 – 0:25] The Hook**: Show cash fan chart. *"Can your business survive its next big decision? Meet WHATIF—the decision simulator that tests your moves across 5,000 futures and grades your forecasts with immutable receipts."*
* **[0:25 – 0:55] The Live Simulation**: Run Diwali scenario. Point out the −₹23.5L cash cliff. *"We proposed ordering 4,000 jars and raising prices for Diwali. In 15 milliseconds, the twin diagnoses a fatal cash cliff in Week 2. Hindsight Cloud pulls up past delivery delays and recommends splitting the order into 1,000-jar batches."*
* **[0:55 – 1:25] The Closed Learning Loop**: Show Decisions ledger and Review modal with confounder tag. *"Every committed forecast is locked. When we review, clean data updates our Bayesian beliefs, while chaotic, noisy weeks are safely gated out."*
* **[1:25 – 2:00] Three Worlds & receipts**: Switch to Agency and Café worlds. Show 81.5% scorecard coverage. *"Three isolated business worlds. Three Hindsight memory banks. Zero hallucinations. Real business experience, verified with receipts."*
