const $ = (selector, parent = document) => parent.querySelector(selector);
const $$ = (selector, parent = document) => [...parent.querySelectorAll(selector)];
const app = $("#app"), title = $("#pageTitle"), modal = $("#modal");
let page = "home", simulation = null, decision = null, memoryOn = true, business = null;

const api = async (path, options = {}) => {
  const response = await fetch(`/api${path}`, {headers: {"Content-Type": "application/json", ...(options.headers || {})}, ...options});
  if (!response.ok) throw new Error((await response.text()).replaceAll('"', "") || "Something went wrong");
  return response.json();
};
const money = (value, signed = false) => `${signed && value > 0 ? "+" : value < 0 ? "−" : ""}₹${Math.abs(value || 0).toLocaleString("en-IN", {maximumFractionDigits: 0})}`;
const pct = value => `${Math.round((value || 0) * 100)}%`;
const escape = text => String(text ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[c]));
function toast(message) { const el = $("#toast"); el.textContent = message; el.classList.add("show"); clearTimeout(window.toastTimer); window.toastTimer = setTimeout(() => el.classList.remove("show"), 2800); }
function setTitle(text) { title.textContent = text; }
function setActiveNav() { $$("[data-page]").forEach(button => button.classList.toggle("active", button.dataset.page === page)); }
function loading(text = "Working through the numbers…") { app.innerHTML = `<div class="loading"><div class="progress">${text}</div><div class="progress">Checking experience and partner reality…</div></div>`; }
function fmtRange(q) { return `${money(q.p10, true)} — ${money(q.p90, true)}`; }
function dateForReview(weeks) { const d = new Date(); d.setDate(d.getDate() + Math.max(7, weeks * 7)); return d.toISOString().slice(0, 10); }

function fanChart(fan) {
  const vals = [...fan.p10, ...fan.p90], min = Math.min(...vals), max = Math.max(...vals), width = 600, height = 205;
  const xy = (value, i) => `${(i / (fan.p50.length - 1)) * width},${height - ((value - min) / Math.max(max - min, 1)) * (height - 18) - 9}`;
  const top = fan.p90.map(xy).join(" "), bottom = [...fan.p10].reverse().map((v, i) => xy(v, fan.p10.length - 1 - i)).join(" "), mid = fan.p50.map(xy).join(" ");
  return `<div class="fan"><svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-label="13-week cash outlook"><path d="M${top} L${bottom} Z" fill="#b9d6c1" opacity=".6"/><polyline points="${mid}" fill="none" stroke="#2b6b52" stroke-width="3"/></svg><div class="chart-legend"><span><b></b>likely cash</span><span><b class="pale"></b>80% range</span></div></div>`;
}

async function refreshHeader() {
  const data = await api("/health"); const memory = data.memory; $("#memoryStatus").textContent = memory.configured ? "Hindsight · memory on" : "Local demo memory";
  if (data.business) {
    const eyebrowEl = $("#businessEyebrow");
    if (eyebrowEl) eyebrowEl.textContent = data.business;
  }
  const sel = $("#worldSelect"); if (sel && data.active_world) sel.value = data.active_world;
  if (sel && !sel.dataset.bound) {
    sel.dataset.bound = "1";
    sel.addEventListener("change", async (e) => {
      const wid = e.target.value;
      try {
        const res = await api(`/worlds/switch?world_id=${encodeURIComponent(wid)}`, {method: "POST"});
        if (res && res.business) {
          const eyebrowEl = $("#businessEyebrow");
          if (eyebrowEl) eyebrowEl.textContent = res.business;
        }
        await refreshHeader();
        toast(`Switched to ${res.business || wid}`);
        navigate(page);
      } catch (err) {
        try {
          const res = await api(`/worlds/switch?world_id=${encodeURIComponent(wid)}`, {method: "GET"});
          if (res && res.business) {
            const eyebrowEl = $("#businessEyebrow");
            if (eyebrowEl) eyebrowEl.textContent = res.business;
          }
          await refreshHeader();
          toast(`Switched to ${res.business || wid}`);
          navigate(page);
        } catch (fErr) { toast(err.message || fErr.message); }
      }
    });
  }
}

async function showHome() {
  setTitle("A clearer next move."); loading("Loading your business outlook…");
  const home = await api("/home"); business = await api("/business"); $("#weekPill").textContent = `week ${home.week}`;
  const eyebrowEl = $("#businessEyebrow"); if (eyebrowEl && home.business) eyebrowEl.textContent = home.business;
  const cash = home.cash, score = home.scorecard, due = home.due;
  const coveredCount = score.records ? score.records.filter(r => r.covered).length : 0;
  const scoreCoverageText = score.gradable_reviews < 6 ? `${coveredCount} of ${score.gradable_reviews} inside stated range.` : `Range coverage: ${pct(score.coverage)}.`;
  app.innerHTML = `<section class="page"><div class="grid two"><div class="ask-bar"><p class="eyebrow" style="color:#bce3c9">Ask a decision question</p><h2>What are you thinking of changing?</h2><form id="quickAsk" class="ask-row"><input id="quickQuestion" aria-label="Decision question" placeholder="e.g. Raise Premium prices 10% for four weeks"/><button>See range →</button></form><div class="chips"><button data-question="Raise Premium prices 10% for four weeks">Raise prices</button><button data-question="Spend 20% more on ads">Spend more on ads</button><button data-question="Run a 10% Core promotion">Run a promotion</button><button data-question="Restock 250 Premium units">Place a restock</button></div></div><div class="card"><p class="label">Cash outlook · next 13 weeks</p><div class="metric"><small>Likely lowest point</small><strong class="${cash.min_value < 0 ? "warn" : "good"}">${money(cash.min_value)} <em style="font:12px var(--sans);letter-spacing:0;color:var(--muted)">in week ${cash.min_week}</em></strong></div>${fanChart(cash.fan)}</div></div><div class="section-heading"><div><h2>Needs your attention</h2><p>The things that make a forecast more honest.</p></div><button class="text-button" data-go="decisions">View ledger →</button></div><div class="grid three"><div class="card"><div class="need"><span class="need-symbol">◷</span><p><b>${due.length} decision${due.length === 1 ? "" : "s"} waiting for review</b><br>${due.length ? "Their locked forecasts are ready to be graded." : "Commit a decision to start your scorecard."}</p></div><button class="text-button" data-go="decisions">Review decisions →</button></div><div class="card"><div class="need"><span class="need-symbol">↗</span><p><b>Reality is a model input</b><br>Log supplier promises so their timing affects cash.</p></div><button class="text-button" data-go="partners">Add a promise →</button></div><div class="card dark"><p class="label" style="color:#b6cabd">Forecast scorecard</p><div class="metric" style="border-color:#365244"><small style="color:#abc0b2">Forecasts graded</small><strong>${score.gradable_reviews}</strong></div><p style="color:#b6cabd;font-size:13px">${scoreCoverageText}</p><button class="text-button" style="color:#bce3c9" data-go="learn">See what changed →</button></div></div></section>`;
  bindAsk(); bindGo();
}

function bindGo() { $$("[data-go]").forEach(b => b.onclick = () => navigate(b.dataset.go)); }
function bindAsk() {
  $("#quickAsk")?.addEventListener("submit", event => { event.preventDefault(); const question = $("#quickQuestion").value.trim(); if (question) openAsk(question); });
  $$("[data-question]").forEach(button => button.onclick = () => openAsk(button.dataset.question));
}

async function openAsk(question = "") {
  page = "ask"; setActiveNav(); setTitle("Ask what if.");
  app.innerHTML = `<section class="page ask-page"><div class="card compose"><p class="label">Decision composer</p><textarea id="question" placeholder="What are you thinking of changing?">${escape(question)}</textarea><div class="compose-footer"><div class="memory-toggle"><button class="${memoryOn ? "active" : ""}" id="memoryYes">Memory on</button><button class="${!memoryOn ? "active" : ""}" id="memoryNo">Memory off</button></div><button class="button primary" id="parseQuestion">Make decision card →</button></div></div><div id="askContent"></div></section>`;
  $("#memoryYes").onclick = () => { memoryOn = true; openAsk($("#question").value); }; $("#memoryNo").onclick = () => { memoryOn = false; openAsk($("#question").value); };
  $("#parseQuestion").onclick = async () => { const q = $("#question").value.trim(); if (!q) return toast("Write a decision first."); try { const parsed = await api("/parse-question", {method:"POST",body:JSON.stringify({question:q})}); decision = parsed.decision; showDecisionCard(); } catch (error) { toast(error.message); } };
  if (question) $("#parseQuestion").click();
}

function showDecisionCard() {
  const content = $("#askContent");
  const bizGroups = (business && business.business && business.business.groups) ? business.business.groups : (business && business.groups ? business.groups : []);
  const groupOptions = bizGroups.length ? bizGroups.map(g => `<option value="${g.key}">${escape(g.name)}</option>`).join("") : `<option value="premium">Premium</option><option value="core">Core</option><option value="gifting">Gifting</option>`;
  content.innerHTML = `<div class="card" style="margin-top:18px"><div class="section-heading" style="margin:0 0 9px"><div><p class="label">Editable decision</p><h2>${escape(decision.title)}</h2></div><span class="chip">${memoryOn ? "Memory On" : "Memory Off"}</span></div><div class="decision-form"><div class="field"><label>Lever</label><select id="lever"><option value="price">Price</option><option value="ads">Ads</option><option value="promotion">Promotion</option><option value="restock">Restock</option></select></div><div class="field"><label>Product group</label><select id="group">${groupOptions}</select></div><div class="field"><label>Change</label><input id="change" type="number" step="1" value="${decision.lever === "restock" ? decision.change : decision.change * 100}"></div><div class="field"><label>Starts week</label><input id="start" type="number" min="0" max="12" value="${decision.start}"></div><div class="field"><label>Duration</label><input id="duration" type="number" min="1" max="13" value="${decision.duration}"></div></div><div style="margin-top:17px;display:flex;justify-content:flex-end"><button class="button primary" id="runSimulation">Run 5,000 simulations →</button></div></div>`;
  $("#lever").value = decision.lever; $("#group").value = decision.group;
  $("#runSimulation").onclick = runSimulation;
}

async function runSimulation() {
  decision = {lever: $("#lever").value, group: $("#group").value, change: Number($("#change").value), start: Number($("#start").value), duration: Number($("#duration").value)};
  if (decision.lever !== "restock") decision.change /= 100;
  loading("Recalling precedents and running 5,000 simulations…");
  try { simulation = await api("/simulate", {method:"POST",body:JSON.stringify({decision,memory_on:memoryOn})}); showResult(); } catch (error) { toast(error.message); openAsk(); }
}

function scenarioCard(item) {
  const q = item.profit_delta, magnitude = Math.max(Math.abs(q.p10), Math.abs(q.p90), 1), left = Math.max(0, 50 + q.p10 / magnitude * 42), right = Math.min(100, 50 + q.p90 / magnitude * 42), width = Math.max(4, right - left);
  return `<article class="scenario ${item.recommended ? "recommended" : ""}">${item.recommended ? '<span class="badge">recommended</span>' : '<span class="badge">scenario</span>'}<h3>${item.name}</h3><div class="money">${money(q.p50,true)}</div><div class="range"><i style="left:${left}%;width:${width}%"></i></div><p>Likely range ${fmtRange(q)}</p><p>${pct(item.loss_chance)} chance worse off · low cash ${money(item.cash.min_value)}</p></article>`;
}

function showResult() {
  setTitle("Here’s the range, not a guess."); const plan = simulation.plan, evidence = simulation.memory.items;
  app.innerHTML = `<section class="page ask-page"><div class="card"><div class="result-hero"><div><p class="label">${escape(simulation.decision.title)} · ${simulation.memory.mode}</p><h2>${escape(simulation.verdict.text)}</h2><p>Lowest likely cash point: <b>${money(plan.cash.min_value)}</b> in week ${plan.cash.min_week}. ${plan.cash.negative_chance ? `${pct(plan.cash.negative_chance)} chance of cash below zero.` : "No simulated cash shortfall in this horizon."}</p></div><div class="memory-toggle"><button class="${memoryOn ? "active" : ""}" id="resultMemoryOn">Memory on</button><button class="${!memoryOn ? "active" : ""}" id="resultMemoryOff">Memory off</button></div></div><div class="scenario-grid">${scenarioCard(simulation.nothing)}${scenarioCard(plan)}${scenarioCard(simulation.test)}</div><details class="evidence" open><summary>Why we think this</summary><div class="grid two" style="margin-top:12px"><div><p class="label">Evidence · ${simulation.memory.source}</p><div class="evidence-list">${evidence.length ? evidence.map(item => `<div class="evidence-item">${escape(item.text)}</div>`).join("") : '<div class="evidence-item">Not enough prior evidence yet. Using a generic starting assumption.</div>'}</div></div><div><p class="label">Three assumptions that matter</p><div class="evidence-list">${simulation.assumptions.map(a => `<div class="evidence-item"><b>${escape(a.name)}</b><br>${Number(a.value).toFixed(a.unit === "days" ? 0 : 2)} ${escape(a.unit)} · ${a.evidence ? `${a.evidence} review${a.evidence===1?"":"s"}` : "starting assumption"}</div>`).join("")}</div></div></div><p style="font-size:12px;color:var(--muted);margin:15px 0 0">${escape(simulation.evidence_note)}</p></details><div class="sticky-actions"><button class="button" id="backToCard">Edit plan</button><button class="button secondary" id="commitTest">Commit test</button><button class="button primary" id="commitPlan">Commit this plan</button></div></div></section>`;
  $("#backToCard").onclick = () => { decision = simulation.decision; openAsk(); showDecisionCard(); }; $("#resultMemoryOn").onclick = () => rerunMemory(true); $("#resultMemoryOff").onclick = () => rerunMemory(false);
  $("#commitPlan").onclick = () => openCommit(false); $("#commitTest").onclick = () => openCommit(true);
}

async function rerunMemory(on) { memoryOn = on; loading(`Re-running with memory ${on ? "on" : "off"}…`); try { simulation = await api("/simulate", {method:"POST",body:JSON.stringify({decision:simulation.decision,memory_on:on})}); showResult(); } catch (err) { toast(err.message); } }

function openCommit(test) {
  const chosen = test ? simulation.test : simulation.plan, d = test ? chosen.decision : simulation.decision;
  const isClear = chosen.profit_delta.p50 > 0 && chosen.loss_chance < .45;
  const defHypo = isClear ? `${d.title} improves profit without a harmful cash dip.` : `Test whether ${d.title} avoids a harmful cash dip despite uncertain central return.`;
  modal.innerHTML = `<form class="modal-card" id="commitForm"><p class="label">Lock a prediction</p><h2>Commit ${test ? "the test" : "this plan"}</h2><p>The prediction is immutable after you confirm it. WHATIF will grade it on the review date.</p><label>Hypothesis<input name="hypothesis" value="${escape(defHypo)}"></label><label>Success rule<input name="success" value="Actual result falls inside the stated 80% range."></label><label>Review date<input name="review" type="date" value="${dateForReview(d.duration)}"></label><div class="modal-actions"><button type="button" class="button" id="cancelModal">Cancel</button><button class="button primary">Lock prediction</button></div></form>`; modal.showModal(); $("#cancelModal").onclick=()=>modal.close();
  $("#commitForm").onsubmit = async event => { event.preventDefault(); const fd = new FormData(event.target); const prediction = test ? {...simulation, plan: simulation.test} : simulation; try { const result = await api("/decisions/commit", {method:"POST",body:JSON.stringify({decision:d,prediction,memory_on:memoryOn,hypothesis:fd.get("hypothesis"),success_rule:fd.get("success"),review_date:fd.get("review")})}); modal.close(); toast("Prediction locked in your decision ledger."); navigate("decisions"); } catch (error) { toast(error.message); } };
}

async function showDecisions() {
  setTitle("Every forecast earns a receipt."); loading("Opening your decision ledger…"); const data = await api("/decisions");
  app.innerHTML = `<section class="page"><div class="section-heading"><div><p class="label">Prediction ledger</p><h2>Locked against the outcome.</h2></div><button class="button primary" id="newDecision">＋ New decision</button></div><div class="card table-wrap">${data.items.length ? `<table class="table"><thead><tr><th>Decision</th><th>Prediction</th><th>Review date</th><th>Status</th><th></th></tr></thead><tbody>${data.items.map(item => { const q=item.prediction.plan.profit_delta; return `<tr><td><b>${escape(item.title)}</b><br><small style="color:var(--muted)">${item.memory_on?"Memory on":"Memory off"}</small></td><td>${money(q.p50,true)}<br><small style="color:var(--muted)">${fmtRange(q)}</small></td><td>${item.review_date}</td><td><span class="status ${item.status}">${item.status}</span></td><td><button class="text-button" data-review="${item.id}">${item.status === "committed" ? "Review →" : "Details →"}</button></td></tr>`; }).join("")}</tbody></table>` : `<div class="empty"><h3>No decisions yet.</h3><p>Ask a what-if, see a range, then lock your prediction here.</p></div>`}</div></section>`;
  $("#newDecision").onclick=()=>openAsk(); $$('[data-review]').forEach(button=>button.onclick=()=>openReview(button.dataset.review));
}

async function openReview(id) {
  const item = await api(`/decisions/${id}`); if (item.status === "reviewed") return openReviewed(item);
  modal.innerHTML = `<form class="modal-card" id="reviewForm"><p class="label">Review ${escape(item.title)}</p><h2>What happened?</h2><p>Your locked central estimate was <b>${money(item.prediction.plan.profit_delta.p50,true)}</b>. Mark unusual weeks so the learning step stays honest.</p><label>Actual profit change (₹)<input required type="number" name="effect" placeholder="e.g. 27000"></label><label>Observed unit change (%)<input type="number" step=".1" name="units" placeholder="e.g. -6"></label><label>Attribution uncertainty (log scale)<input type="number" step=".01" min="0" max="2" name="uncertainty" value="0.10"></label><label>Unusual events, comma-separated<input name="tags" placeholder="festival, stockout, ad issue"></label><label>Owner note<textarea name="note" placeholder="What else changed?"></textarea></label><div class="modal-actions"><button type="button" class="button" id="cancelModal">Cancel</button><button class="button primary">Grade forecast</button></div></form>`; modal.showModal(); $("#cancelModal").onclick=()=>modal.close();
  $("#reviewForm").onsubmit=async event=>{event.preventDefault();const f=new FormData(event.target);try{const done=await api(`/decisions/${id}/review`,{method:"POST",body:JSON.stringify({actual_effect:Number(f.get("effect")),observed_unit_change:f.get("units")===""?null:Number(f.get("units")),uncertainty:Number(f.get("uncertainty")),tags:f.get("tags").split(",").map(x=>x.trim()).filter(Boolean),note:f.get("note")})});modal.close();openReviewed(done.decision);}catch(e){toast(e.message)}};
}

function openReviewed(item) { const out=item.outcome, changes=out.changes||[]; modal.innerHTML=`<div class="modal-card"><p class="label">Reviewed decision</p><h2>${escape(item.title)}</h2><p><b>${money(out.actual_effect,true)}</b> actual estimate · ${out.gradable ? (out.covered?"inside the stated range":"outside the stated range") : "recorded, not graded"}</p><div class="evidence-list">${out.learned ? changes.map(c=>`<div class="evidence-item"><b>${escape(c.name)}</b><br>${Number(c.before.mean).toFixed(2)} → ${Number(c.after.mean).toFixed(2)}</div>`).join("") : `<div class="evidence-item">${escape(out.reason || "No belief was changed.")}</div>`}</div><div class="modal-actions"><button class="button primary" id="closeReviewed">Done</button></div></div>`;modal.showModal();$("#closeReviewed").onclick=()=>{modal.close();showDecisions()}; }

async function showPartners() {
  setTitle("Model what partners really do."); loading("Loading partner reality…"); const data = await api("/partners");
  app.innerHTML=`<section class="page"><div class="grid two"><div class="card"><p class="label">Capture a promise</p><h2 style="font:500 25px var(--serif);margin:0 0 8px">Paste the actual message.</h2><p style="color:var(--muted);font-size:13px">WHATIF extracts who, what, when and hedge words. The original quote stays attached.</p><textarea id="promiseMessage" style="width:100%;min-height:100px;padding:11px;border:1px solid var(--line);border-radius:7px" placeholder="Rajan: jars should be ready in 10 days, hopefully Friday."></textarea><div style="display:flex;justify-content:flex-end;margin-top:10px"><button class="button primary" id="addPromise">Add promise</button></div></div><div class="card dark"><p class="label" style="color:#b6cabd">Why this changes simulation</p><h3 style="font:500 23px var(--serif);margin:5px 0">Promises become cash timing.</h3><p style="color:#c2d2c4">A late supplier causes stockouts. A slow courier changes when sales turn into cash. WHATIF uses each resolved promise to narrow the reality layer.</p></div></div><div class="section-heading"><div><h2>Partner profiles</h2><p>What they say, versus what happens.</p></div></div><div class="partner-list">${data.items.map(p=>`<article class="partner"><span class="partner-icon">${p.type === "courier" ? "↗" : "□"}</span><div style="flex:1"><h3>${escape(p.name)}</h3><p>says ${p.promised_days.toFixed(0)} days, delivers about <b>${p.expected_days.toFixed(0)} days</b> · ${p.observations ? `based on ${p.observations} resolved promise${p.observations===1?"":"s"}` : "using a similar-partner starting assumption"}</p>${p.promises.filter(x=>x.delivered_days===null).map(x=>`<button class="text-button" data-deliver="${x.id}" style="margin-top:5px">Mark “${escape(x.item)}” delivered →</button>`).join("")}</div><span class="reliability">${p.reliability}</span></article>`).join("")}</div></section>`;
  $("#addPromise").onclick=async()=>{const message=$("#promiseMessage").value.trim();if(!message)return toast("Paste a promise message first.");try{const result=await api("/promises",{method:"POST",body:JSON.stringify({message})});toast(`${result.preview.partner_name} promise captured.`);showPartners()}catch(e){toast(e.message)}}; $$('[data-deliver]').forEach(b=>b.onclick=()=>openDeliver(b.dataset.deliver));
}

function openDeliver(id){modal.innerHTML=`<form class="modal-card" id="deliverForm"><p class="label">Resolve promise</p><h2>When did it actually arrive?</h2><label>Actual delivery time (days)<input required autofocus name="days" type="number" min="1" step=".5"></label><div class="modal-actions"><button type="button" class="button" id="cancelModal">Cancel</button><button class="button primary">Update reality</button></div></form>`;modal.showModal();$("#cancelModal").onclick=()=>modal.close();$("#deliverForm").onsubmit=async e=>{e.preventDefault();try{await api(`/promises/${id}/deliver`,{method:"POST",body:JSON.stringify({actual_days:Number(new FormData(e.target).get("days"))})});modal.close();toast("Partner belief updated.");showPartners()}catch(x){toast(x.message)}}}

async function showLearn() {
  setTitle("Learning, shown plainly."); loading("Building scorecard…");
  const [score, beliefs, health] = await Promise.all([api("/scorecard"), api("/beliefs"), api("/health")]);
  if (health && health.business) {
    const eyebrowEl = $("#businessEyebrow");
    if (eyebrowEl) eyebrowEl.textContent = health.business;
  }
  app.innerHTML=`<section class="page"><div class="tabs"><button class="active" id="scoreTab">Scorecard</button><button id="beliefTab">Beliefs</button></div><div id="learnContent"></div></section>`;
  const renderScore=()=>{
    const coveredCount = score.records ? score.records.filter(r => r.covered).length : 0;
    const relVal = score.gradable_reviews === 0 ? "—" : (score.gradable_reviews < 6 ? `${coveredCount} of ${score.gradable_reviews}` : pct(score.coverage));
    const relSub = score.gradable_reviews < 6 ? "Show counts below 6 reviews." : "Stated range target: 80%.";
    $("#learnContent").innerHTML=`<div class="grid three"><div class="card"><p class="label">Forecasts graded · ${escape(health.business || "Business")}</p><div class="money">${score.gradable_reviews}</div><p style="color:var(--muted);font-size:13px">${score.gradable_reviews < 6 ? "Counts only while evidence is thin." : "Enough reviews to assess coverage."}</p></div><div class="card"><p class="label">Median error</p><div class="money">${score.median_absolute_error===null?"—":money(score.median_absolute_error)}</div><p style="color:var(--muted);font-size:13px">Central estimate versus attributed outcome.</p></div><div class="card"><p class="label">Range reliability</p><div class="money">${relVal}</div><p style="color:var(--muted);font-size:13px">${relSub}</p></div></div><div class="card" style="margin-top:18px"><div class="section-heading" style="margin:0 0 15px"><div><p class="label">Calibration log · ${escape(health.business || "Business")}</p><h2>How the forecast held up.</h2></div><div style="display:flex;gap:8px"><button class="button" id="revealTruth">Reveal synthetic truth</button><button class="button secondary" id="askWhy">Why were we off?</button></div></div>${score.records.length?`<table class="table"><thead><tr><th>Decision</th><th>Predicted</th><th>Actual</th><th>Range held</th></tr></thead><tbody>${score.records.map(r=>`<tr><td>${escape(r.title)}</td><td>${money(r.p50,true)}</td><td>${money(r.actual,true)}</td><td>${r.covered?"✓ inside":"× outside"}</td></tr>`).join("")}</tbody></table>`:`<div class="empty">No graded outcomes yet for ${escape(health.business || "this business")}. Commit then review a decision to start the scorecard.</div>`}</div>`;$("#askWhy").onclick=reflectWhy;$("#revealTruth").onclick=revealTruth};
  const renderBeliefs=()=>{$("#learnContent").innerHTML=`<div class="card"><div class="section-heading" style="margin:0 0 10px"><div><p class="label">What the model currently believes · ${escape(health.business || "Business")}</p><h2>Starting assumptions become evidence.</h2></div><span class="chip">${beliefs.memory.mode}</span></div>${beliefs.items.map(b=>`<article class="belief"><div><h3>${escape(b.label)}</h3><p>${escape(b.sentence)}</p><div class="bar"><i style="width:${Math.min(100,20+b.n*16)}%"></i></div><small style="color:var(--muted)">${b.source === "prior"?"Starting assumption":`Learned from ${b.n} event${b.n===1?"":"s"}`}</small></div><div><button class="text-button" data-forget="${escape(b.name)}">Forget</button></div></article>`).join("")}</div>`;$$('[data-forget]').forEach(x=>x.onclick=async()=>{if(!confirm(`Reset ${x.dataset.forget} to its starting assumption?`))return;await api(`/beliefs/${encodeURIComponent(x.dataset.forget)}/forget`,{method:"POST"});toast("Belief reset to generic prior.");showLearn()})};
  renderScore(); $("#scoreTab").onclick=()=>{$("#scoreTab").classList.add("active");$("#beliefTab").classList.remove("active");renderScore()};$("#beliefTab").onclick=()=>{$("#beliefTab").classList.add("active");$("#scoreTab").classList.remove("active");renderBeliefs()};
}

async function reflectWhy(){try{const r=await api("/reflect",{method:"POST"});modal.innerHTML=`<div class="modal-card"><p class="label">${escape(r.source)} reflection</p><h2>Why were we off?</h2><p>${escape(r.text)}</p><div class="modal-actions"><button class="button primary" id="closeReflection">Done</button></div></div>`;modal.showModal();$("#closeReflection").onclick=()=>modal.close()}catch(e){toast(e.message)}}

async function revealTruth(){try{const truth=await api("/demo/ground-truth");modal.innerHTML=`<div class="modal-card"><p class="label">Synthetic-demo reveal</p><h2>Hidden ground truth</h2><p>${escape(truth.note)}</p><div class="evidence-list">${Object.entries(truth).filter(([key])=>key!=="note").map(([key,value])=>`<div class="evidence-item"><b>${escape(key.replaceAll("_"," "))}</b><br>${escape(value)}</div>`).join("")}</div><div class="modal-actions"><button class="button primary" id="closeTruth">Done</button></div></div>`;modal.showModal();$("#closeTruth").onclick=()=>modal.close()}catch(e){toast(e.message)}}

async function navigate(next) { page = next; window.location.hash = next; setActiveNav(); if(next==="home")return showHome();if(next==="decisions")return showDecisions();if(next==="partners")return showPartners();if(next==="learn")return showLearn(); }
$$("[data-page]").forEach(button => button.onclick = () => navigate(button.dataset.page)); $("#askFab").onclick=()=>openAsk();$("#mobileAsk").onclick=()=>openAsk();$("#advanceDemo").onclick=async()=>{try{const r=await api("/demo/advance?step=1",{method:"POST"});$("#weekPill").textContent=`week ${r.week}`;toast(r.message);if(page==="home")showHome()}catch(e){toast(e.message)}};
window.addEventListener("hashchange", () => {
  const hash = window.location.hash.replace("#", "");
  if (hash && hash !== page) navigate(hash);
});
const initPage = window.location.hash.replace("#", "") || "home";
refreshHeader().catch(()=>{}); navigate(initPage);
