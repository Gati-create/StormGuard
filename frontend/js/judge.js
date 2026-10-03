// Judge Mode — distraction-free presentation engine.
// 10 scripted stages over a deterministic baseline; one live simulation.

import { api } from "./api.js";
import { fmtINR, fmtINRFull, fmtNum, fmtPct } from "./format.js";
import { esc, badge, statusPill, toastError } from "./components.js";
import { renderCityMap, levelColor } from "./map.js";
import { svgGauge, svgHBars, C } from "./charts.js";
import { saveSimulation } from "./store.js";

const STAGE_TITLES = [
  "NORMAL CONDITIONS", "EXTREME WEATHER", "AI RISK DETECTION", "RIDER EXPOSURE",
  "PARAMETRIC TRIGGER", "ELIGIBILITY", "FRAUD CHECK", "PAYOUT",
  "PLATFORM FINANCIAL IMPACT", "BUSINESS VIABILITY",
];

const S = {
  script: [], baseline: null, overview: null, sim: null,
  viability: null, sensitivity: null,
  idx: 0, playing: false, timer: null, animating: false, open: false,
};

let keyHandler = null;

export function isPresenting() { return S.open; }

export async function enterPresentationMode() {
  const root = document.getElementById("stage-root");
  if (!root) return;
  root.classList.add("open");
  document.body.classList.add("presenting");
  S.open = true;
  root.innerHTML = stageLoader("Resetting to the deterministic baseline…");
  let startResp;
  try {
    startResp = await api.post("/api/judge/start", {});
  } catch (err) {
    exitPresentationMode();
    toastError(err.detail || "Could not start judge mode");
    return;
  }
  if (!S.open) return;
  S.script = Array.isArray(startResp.script) ? startResp.script : [];
  S.baseline = startResp.baseline_cards || null;
  S.overview = null; S.sim = null; S.viability = null; S.sensitivity = null;
  S.idx = 0; S.playing = false;
  bindKeys();
  goToStage(0);
}

export function exitPresentationMode() {
  stopTimer();
  S.playing = false;
  S.open = false;
  S.animating = false;
  if (keyHandler) {
    document.removeEventListener("keydown", keyHandler);
    keyHandler = null;
  }
  const root = document.getElementById("stage-root");
  if (root) {
    root.classList.remove("open");
    root.innerHTML = "";
  }
  document.body.classList.remove("presenting");
  // Shell data changed (baseline reset / new event) — refresh the underlying view.
  window.dispatchEvent(new HashChangeEvent("hashchange"));
}

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------

function bindKeys() {
  if (keyHandler) document.removeEventListener("keydown", keyHandler);
  keyHandler = function (e) {
    if (e.key === "ArrowRight") { e.preventDefault(); nextStage(); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); prevStage(); }
    else if (e.key === "Escape") { e.preventDefault(); exitPresentationMode(); }
    else if (e.key === " ") { e.preventDefault(); togglePlay(); }
  };
  document.addEventListener("keydown", keyHandler);
}

function nextStage() { if (S.idx < 9) goToStage(S.idx + 1); else setPlaying(false); }
function prevStage() { if (S.idx > 0) goToStage(S.idx - 1); }

function setPlaying(on) {
  S.playing = on;
  stopTimer();
  if (on) {
    S.timer = setTimeout(function () { nextStage(); }, 6000);
  }
  const btn = document.querySelector("#jm-play");
  if (btn) btn.innerHTML = on ? "⏸ PAUSE" : "▶ AUTO";
}

function togglePlay() { setPlaying(!S.playing); }
function stopTimer() { if (S.timer) { clearTimeout(S.timer); S.timer = null; } }

async function goToStage(idx) {
  stopTimer();
  S.animating = false;
  S.idx = idx;
  const root = document.getElementById("stage-root");
  if (!root || !S.open) return;

  // Data prerequisites per stage.
  try {
    if (idx === 0 && !S.overview) {
      root.innerHTML = stageLoader("Loading baseline…");
      S.overview = await api.get("/api/overview");
    } else if (idx === 1 && !S.sim) {
      root.innerHTML = stageLoader("Black Rainstorm is hitting Mong Kok…");
      await runJudgeSim();
    } else if (idx >= 2 && idx <= 8 && !S.sim) {
      root.innerHTML = stageLoader("Running the canonical event first…");
      await runJudgeSim();
    } else if (idx === 9 && !S.viability) {
      root.innerHTML = stageLoader("Computing viability…");
      const v = await api.post("/api/viability", {});
      const sens = await api.post("/api/viability/sensitivity", {
        base: (v && v.inputs) || {},
        shocks: [{ key: "weekly_event_probability", mult: 1.25, label: "Severe weather +25%" }],
      });
      S.viability = v;
      S.sensitivity = sens;
    }
  } catch (err) {
    if (!S.open) return;
    root.innerHTML = stageLoader("⚠ " + esc(err.detail || "Stage failed to load") +
      ' <button class="btn btn-accent btn-sm" id="jm-retry" style="margin-left:12px">Retry</button>');
    const r = document.getElementById("jm-retry");
    if (r) r.addEventListener("click", function () { goToStage(idx); });
    return;
  }
  if (!S.open) return;
  renderStage(root);
  if (S.playing) {
    // Re-arm auto-advance (longer while the pipeline animates).
    S.timer = setTimeout(function () { nextStage(); }, idx === 1 ? 9000 : 6000);
  }
}

async function runJudgeSim() {
  const resp = await api.post("/api/simulate", { scenario_key: "EXTREME_FLOOD", zone_id: "Z-MK" });
  S.sim = resp;
  saveSimulation(resp);
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

function stageLoader(msg) {
  return '<div class="jm-loader"><span class="spinner"></span><span>' + msg + "</span></div>";
}

function renderStage(root) {
  const idx = S.idx;
  root.innerHTML =
    '<div class="jm-stage">' +
      '<header class="jm-top">' +
        '<div class="jm-dots">' + STAGE_TITLES.map(function (t, i) {
          return '<button class="jm-dot' + (i === idx ? " active" : (i < idx ? " done" : "")) + '" data-stage="' + i + '" title="' + esc(t) + '"></button>';
        }).join("") + "</div>" +
        '<div class="jm-count">' + (idx + 1) + " / 10</div>" +
      "</header>" +
      '<div class="jm-kicker">' + esc(STAGE_TITLES[idx]) + "</div>" +
      '<h1 class="jm-headline">' + esc(narration("headline", idx)) + "</h1>" +
      '<p class="jm-body">' + esc(narration("body", idx)) + "</p>" +
      '<div class="jm-content" id="jm-content"></div>' +
      '<div class="jm-explainer" id="jm-explainer"></div>' +
      '<footer class="jm-controls">' +
        '<button class="btn btn-ghost" id="jm-prev">◀ PREV</button>' +
        '<button class="btn btn-accent" id="jm-play">▶ AUTO</button>' +
        '<button class="btn btn-ghost" id="jm-next">NEXT ▶</button>' +
        '<span class="jm-skip">' +
          '<button class="chip-btn" data-skip="6">SKIP TO FRAUD</button>' +
          '<button class="chip-btn" data-skip="7">SKIP TO PAYOUT</button>' +
          '<button class="chip-btn" data-skip="9">SKIP TO BUSINESS</button>' +
        "</span>" +
        '<button class="btn btn-ghost" id="jm-exit">✕ EXIT</button>' +
      "</footer>" +
    "</div>";

  document.getElementById("jm-prev").addEventListener("click", prevStage);
  document.getElementById("jm-next").addEventListener("click", nextStage);
  document.getElementById("jm-play").addEventListener("click", togglePlay);
  document.getElementById("jm-exit").addEventListener("click", exitPresentationMode);
  Array.prototype.forEach.call(root.querySelectorAll(".jm-dot"), function (d) {
    d.addEventListener("click", function () { goToStage(Number(d.getAttribute("data-stage"))); });
  });
  Array.prototype.forEach.call(root.querySelectorAll("[data-skip]"), function (b) {
    b.addEventListener("click", function () { goToStage(Number(b.getAttribute("data-skip"))); });
  });

  const content = document.getElementById("jm-content");
  renderStageContent(content, idx);
  document.getElementById("jm-explainer").innerHTML = explainerHtml(idx);
  if (S.playing) {
    const btn = document.getElementById("jm-play");
    if (btn) btn.innerHTML = "⏸ PAUSE";
  }
}

function narration(field, idx) {
  const step = S.script[idx] || {};
  const n = step.narration || {};
  if (n[field]) return n[field];
  const fallback = {
    headline: ["A normal delivery day in Hong Kong", "Extreme weather arrives", "The risk engine scores every zone",
      "Thousands of riders are exposed", "Objective thresholds breach", "Active policies are matched",
      "Anomaly scoring in milliseconds", "Instant FPS payout (simulated)", "The ledger updates live", "The model is sustainable"],
    body: ["", "", "", "", "", "", "", "", "", ""],
  };
  return fallback[field][idx] || "";
}

function renderStageContent(content, idx) {
  switch (idx) {
    case 0: return stageNormal(content);
    case 1: return stageEvent(content);
    case 2: return stageRisk(content);
    case 3: return stageExposure(content);
    case 4: return stageTrigger(content);
    case 5: return stageEligibility(content);
    case 6: return stageFraud(content);
    case 7: return stagePayout(content);
    case 8: return stageFinance(content);
    case 9: return stageViability(content);
    default: content.innerHTML = "";
  }
}

function jmStat(label, value, sub, tone) {
  return '<div class="jm-stat' + (tone ? " tone-" + tone : "") + '">' +
    '<div class="jm-stat-value">' + esc(value) + "</div>" +
    '<div class="jm-stat-label">' + esc(label) + "</div>" +
    (sub ? '<div class="jm-stat-sub">' + esc(sub) + "</div>" : "") + "</div>";
}

function stageNormal(content) {
  const ov = S.overview || {};
  const cards = ov.cards || {};
  content.innerHTML =
    '<div class="jm-stats">' +
      jmStat("RIDERS COVERED", fmtNum(cards.riders), "active weekly policies") +
      jmStat("PORTFOLIO RISK", (cards.portfolio_risk === undefined ? "—" : cards.portfolio_risk + "/100"), "all zones within appetite", "ok") +
      jmStat("PREMIUM THIS WEEK", fmtINR(S.baseline ? S.baseline.premium_collected : null), "collected from platform + riders") +
      jmStat("ACTIVE EVENTS", "0", "conditions normal", "ok") +
    "</div>" +
    '<div class="jm-map">' + renderCityMap(ov.map_zones || [], {}) + "</div>" +
    '<div class="jm-badge-row">' + badge("SIMULATED") + " " + badge("MOCK DATA") + "</div>";
}

function stageEvent(content) {
  const sim = S.sim || {};
  const stages = Array.isArray(sim.stages) ? sim.stages : [];
  const w = stages.length ? stages[0] : null;
  content.innerHTML =
    '<div class="jm-stats">' +
      jmStat("RAINFALL", "95 mm", "in 4 hours", "warn") +
      jmStat("FLOOD PROBABILITY", "82%", "Mong Kok epicenter", "warn") +
      jmStat("EVENT TYPE", "BLACK RAINSTORM", "parametric feed (simulated)") +
      jmStat("ZONES SCORED", "10", "signal fanned out city-wide") +
    "</div>" +
    '<div class="jm-pipeline" id="jm-pipeline">' +
      stages.map(function (st, i) {
        return '<div class="jm-pipe-row pending" data-i="' + i + '">' +
          '<span class="jm-pipe-check">✓</span>' +
          '<span class="jm-pipe-title">' + esc(st.title || st.key) + "</span>" +
          '<span class="jm-pipe-summary">' + esc(st.summary || "") + "</span>" +
        "</div>";
      }).join("") +
    "</div>";
  // Animate the pipeline: flip each row to done.
  S.animating = true;
  const rows = content.querySelectorAll(".jm-pipe-row");
  let i = 0;
  function flip() {
    if (!S.open || !content.isConnected) return;
    if (i >= rows.length) { S.animating = false; return; }
    rows[i].classList.remove("pending");
    rows[i].classList.add("done");
    i += 1;
    setTimeout(flip, 620);
  }
  setTimeout(flip, 350);
}

function stageRisk(content) {
  const a = (S.sim && S.sim.assessment) || {};
  const color = levelColor(a.risk_level);
  const factors = Array.isArray(a.risk_factors) ? a.risk_factors.slice(0, 5) : [];
  const maxPts = Math.max.apply(null, factors.map(function (f) { return Number(f.points) || 0; }).concat([1]));
  content.innerHTML =
    '<div class="jm-split">' +
      '<div class="jm-gauge">' + svgGauge({
        value: a.risk_score || 0, max: 100, label: a.risk_level || "—",
        sub: "epicenter · " + (a.zone_name || ""), color: color,
      }) + "</div>" +
      '<div class="jm-factors">' +
        factors.map(function (f) {
          const w = Math.max(4, Math.round(((Number(f.points) || 0) / maxPts) * 100));
          return '<div class="factor-row jm-factor"><span class="factor-label">' + esc(f.label) + "</span>" +
            '<span class="factor-bar"><span class="factor-fill" style="width:' + w + "%;background:" + color + '"></span></span>' +
            '<span class="factor-pts">+' + esc(f.points) + "</span></div>";
        }).join("") +
        '<p class="jm-note">' + esc(a.explanation || "") + "</p>" +
        '<p class="jm-note muted-text">Model ' + esc(a.model_version || "") + " · confidence " + esc(fmtPct(a.confidence_score, 0)) + " · DEMO MODEL — not trained on real insurance data</p>" +
      "</div>" +
    "</div>";
}

function stageExposure(content) {
  const t = (S.sim && S.sim.totals) || {};
  const zones = (S.sim && Array.isArray(S.sim.zones) ? S.sim.zones : []).filter(function (z) {
    return Number(z.affected_riders) > 0;
  });
  content.innerHTML =
    '<div class="jm-stats">' +
      jmStat("RIDERS EXPOSED", fmtNum(t.affected_riders), "home zone fired a trigger", "warn") +
      jmStat("ZONES AFFECTED", String(zones.length), "of 10 city zones") +
      jmStat("INCOME AT RISK", fmtINR(t.income_exposure), "expected lost earnings", "danger") +
      jmStat("DEMO RIDER LOSS", fmtINRFull(620), "Arjun K. · W-000001 · STANDARD") +
    "</div>" +
    '<div class="jm-chart">' + svgHBars({
      rows: zones.map(function (z) { return { label: z.name, value: z.affected_riders }; }),
      fmt: fmtNum, color: C.orange, labelWidth: 140,
    }) + "</div>";
}

function stageTrigger(content) {
  const st = stageByKey("TRIGGER");
  const metrics = (st && st.metrics) || {};
  const fired = Array.isArray(metrics.fired_types) ? metrics.fired_types : ["EXTREME_RAIN_FLOOD"];
  content.innerHTML =
    '<div class="jm-trigger-card">' +
      '<div class="jm-trigger-icon">⚡</div>' +
      '<div class="jm-trigger-type">' + esc(fired.join(" + ") || "—") + "</div>" +
      '<div class="jm-trigger-conds">' +
        '<span class="jm-cond met">rainfall 95mm ≥ 90mm ✓</span>' +
        '<span class="jm-cond met">flood probability 82% ≥ 75% ✓</span>' +
        '<span class="jm-cond">' + esc(metrics.evaluated !== undefined ? metrics.evaluated + " rule evaluations across 10 zones" : "") + "</span>" +
      "</div>" +
      '<p class="jm-note">' + esc((st && st.detail) || "") + "</p>" +
    "</div>";
}

function stageEligibility(content) {
  const t = (S.sim && S.sim.totals) || {};
  const eligible = Number(t.eligible_riders) || 0;
  const affected = Number(t.affected_riders) || 1;
  const pct = Math.round((eligible / Math.max(1, affected)) * 100);
  content.innerHTML =
    '<div class="jm-stats">' +
      jmStat("ELIGIBLE", fmtNum(eligible), "ACTIVE weekly policy + triggered zone", "ok") +
      jmStat("AFFECTED", fmtNum(affected), "in the event footprint") +
      jmStat("MATCH RATE", pct + "%", "rest: expired/missing policy, logged with reasons") +
      jmStat("DUPLICATES", "0", "idempotency keys block double claims", "ok") +
    "</div>" +
    '<div class="split-bar jm-splitbar"><div class="split-seg split-platform" style="width:' + pct + '%">ELIGIBLE ' + esc(fmtNum(eligible)) + "</div>" +
    '<div class="split-seg split-worker" style="width:' + (100 - pct) + '%">EXCLUDED ' + esc(fmtNum(affected - eligible)) + "</div></div>";
}

function stageFraud(content) {
  const t = (S.sim && S.sim.totals) || {};
  const heldRate = Number(t.approved) + Number(t.held) > 0 ?
    (Number(t.held) / (Number(t.approved) + Number(t.held))) : 0;
  content.innerHTML =
    '<div class="jm-stats">' +
      jmStat("AUTO-APPROVED", fmtNum(t.approved), "below the fraud hold threshold", "ok") +
      jmStat("HELD FOR REVIEW", fmtNum(t.held), "a human risk manager decides", "warn") +
      jmStat("HOLD RATE", fmtPct(heldRate), "≈ baseline suspicious rate") +
      jmStat("AUTO-REJECTED", "0", "the engine never auto-accuses", "ok") +
    "</div>" +
    '<p class="jm-note">Additive anomaly scoring across 8 signals — GPS mismatch, impossible travel, duplicates, frequency, zone mismatch and more. ' +
    "Scores ≥ 60 wait for a human; every review is audit-logged.</p>";
}

function stagePayout(content) {
  const t = (S.sim && S.sim.totals) || {};
  const ri = (S.sim && S.sim.rider_impact) || null;
  content.innerHTML =
    '<div class="jm-stats">' +
      jmStat("TOTAL PAYOUT", fmtINR(t.expected_payout), "pushed instantly", "teal") +
      jmStat("RIDERS PAID", fmtNum(t.approved), "FPS (SIMULATED)") +
      jmStat("AVG PAYOUT", fmtINR(t.avg_payout), "per approved claim") +
      jmStat("DOUBLE PAYMENTS", "0", "idempotency keys", "ok") +
    "</div>" +
    (ri ?
      '<div class="jm-rider-card">' +
        '<span class="jm-rider-loss">Arjun K. loses ' + esc(fmtINRFull(ri.estimated_income_loss)) + " of income</span>" +
        '<span class="jm-rider-arrow">→</span>' +
        '<span class="jm-rider-gain">receives ' + esc(fmtINRFull(ri.protection_payout)) + "</span>" +
        statusPill(ri.status || "PAID") +
        '<span class="jm-rider-label">' + esc(ri.payment_label || "") + "</span>" +
      "</div>" : "");
}

function stageFinance(content) {
  const after = (S.sim && S.sim.fleet_cards) || {};
  const before = S.baseline || {};
  const finStage = stageByKey("FINANCE");
  const m = (finStage && finStage.metrics) || {};
  function row(label, b, a, fmt) {
    return '<div class="jm-fin-row"><span class="jm-fin-label">' + esc(label) + "</span>" +
      '<span class="jm-fin-before">' + esc(fmt(b)) + '</span><span class="jm-fin-arrow">→</span>' +
      '<span class="jm-fin-after">' + esc(fmt(a)) + "</span></div>";
  }
  content.innerHTML =
    '<div class="jm-fin">' +
      row("Premium collected (week)", before.premium_collected, after.premium_collected, fmtINR) +
      row("Claims paid (week)", before.claims_paid, after.claims_paid, fmtINR) +
      row("Loss ratio", m.loss_ratio_before !== undefined ? m.loss_ratio_before : before.loss_ratio,
        after.loss_ratio, function (v) { return fmtPct(v); }) +
      row("Fraud prevented (season)", before.fraud_prevented, after.fraud_prevented, fmtINR) +
    "</div>" +
    '<p class="jm-note">' + esc((finStage && finStage.detail) || "") + "</p>";
}

function stageViability(content) {
  const v = S.viability || {};
  const w = v.weekly || {};
  const sensRows = (S.sensitivity && S.sensitivity.results) || [];
  const shock = sensRows.length ? sensRows[0] : null;
  content.innerHTML =
    '<div class="jm-stats">' +
      jmStat("PREMIUM REVENUE", fmtINR(w.premium_revenue), "per week") +
      jmStat("EXPECTED CLAIMS", fmtINR(w.expected_claims), "per week", "warn") +
      jmStat("GROSS CONTRIBUTION", fmtINR(w.gross_contribution), "per week after all costs", Number(w.gross_contribution) >= 0 ? "teal" : "danger") +
      jmStat("LOSS RATIO", fmtPct(w.loss_ratio), "claims ÷ premiums") +
      jmStat("BREAK-EVEN", v.break_even_riders ? fmtNum(v.break_even_riders) + " riders" : "—", "fleet is 12,482", "ok") +
    "</div>" +
    (shock ?
      '<p class="jm-note">Stress: ' + esc(shock.label) + " → loss ratio " + esc(fmtPct(shock.loss_ratio)) +
        ", annual contribution " + esc(fmtINR(shock.annual_contribution)) + " — the model stays viable under shock.</p>" : "");
}

function stageByKey(key) {
  const stages = (S.sim && Array.isArray(S.sim.stages)) ? S.sim.stages : [];
  for (let i = 0; i < stages.length; i += 1) {
    if (stages[i].key === key) return stages[i];
  }
  return null;
}

// ---------------------------------------------------------------------------
// 5-line explainer per stage
// ---------------------------------------------------------------------------

function explainerHtml(idx) {
  const lines = explainerLines(idx);
  return '<div class="jm-expl-grid">' + lines.map(function (l) {
    return '<div class="jm-expl-row"><span class="jm-expl-q">' + esc(l.q) + '</span><span class="jm-expl-a">' + esc(l.a) + "</span></div>";
  }).join("") + "</div>";
}

function explainerLines(idx) {
  const t = (S.sim && S.sim.totals) || {};
  const a = (S.sim && S.sim.assessment) || {};
  const ov = S.overview || {};
  const cards = ov.cards || {};
  const ri = (S.sim && S.sim.rider_impact) || {};
  const v = (S.viability && S.viability.weekly) || {};
  switch (idx) {
    case 0: return [
      { q: "WHAT HAPPENED?", a: fmtNum(cards.riders) + " gig riders are covered this week across 10 Hong Kong districts; conditions are normal." },
      { q: "WHY DID IT HAPPEN?", a: "Weekly micro-premiums are priced from zone risk in advance — protection is always on, rain or shine." },
      { q: "WHAT DID THE AI DO?", a: "Ambient scoring keeps every zone under continuous watch (portfolio risk " + (cards.portfolio_risk || "—") + "/100)." },
      { q: "WHAT DID THE BUSINESS DO?", a: "Collected " + fmtINR(S.baseline ? S.baseline.premium_collected : null) + " of premiums and holds them ready for the next disruption." },
      { q: "WHAT DID THE RIDER RECEIVE?", a: "Silent, always-on income protection for ≤ HK$45/week — no action needed." },
    ];
    case 1: return [
      { q: "WHAT HAPPENED?", a: "A simulated weather feed reports 95mm of rain in 4 hours over Mong Kok with an 82% flood probability." },
      { q: "WHY DID IT HAPPEN?", a: "Monsoon season over a low-lying, high-density delivery zone — the exact scenario parametric cover exists for." },
      { q: "WHAT DID THE AI DO?", a: "Persisted the event, fanned the signal out to all 10 zones with propensity-based attenuation, and started the pipeline." },
      { q: "WHAT DID THE BUSINESS DO?", a: "Nothing manual — the system reacts on its own, in milliseconds." },
      { q: "WHAT DID THE RIDER RECEIVE?", a: "Nothing yet — riders are still completing deliveries as the rain builds." },
    ];
    case 2: return [
      { q: "WHAT HAPPENED?", a: "Epicenter risk jumps to " + (a.risk_score || "—") + "/100 (" + (a.risk_level || "—") + ")." },
      { q: "WHY DID IT HAPPEN?", a: topFactorsText(a) },
      { q: "WHAT DID THE AI DO?", a: "Scored every zone with a deterministic additive model — every point on the score is itemised and explainable." },
      { q: "WHAT DID THE BUSINESS DO?", a: "Gained a quantified view of the event before a single rupee moved." },
      { q: "WHAT DID THE RIDER RECEIVE?", a: "—" },
    ];
    case 3: return [
      { q: "WHAT HAPPENED?", a: fmtNum(t.affected_riders) + " riders in the triggered zones are exposed; " + fmtINR(t.income_exposure) + " of income is at risk." },
      { q: "WHY DID IT HAPPEN?", a: "Their home zones fired at least one parametric trigger during their working window." },
      { q: "WHAT DID THE AI DO?", a: "Matched riders to expected lost hours using duration × disruption multiplier × schedule overlap." },
      { q: "WHAT DID THE BUSINESS DO?", a: "Sized the liability in seconds instead of days of claims adjustment." },
      { q: "WHAT DID THE RIDER RECEIVE?", a: "Arjun K. (W-000001) stands to lose " + fmtINRFull(ri.estimated_income_loss || 620) + " of this week's income." },
    ];
    case 4: return [
      { q: "WHAT HAPPENED?", a: "EXTREME_RAIN_FLOOD fires: objective thresholds breached at the epicenter." },
      { q: "WHY DID IT HAPPEN?", a: "Rainfall 95mm ≥ 90mm and flood probability 82% ≥ 75% — published, pre-agreed rules." },
      { q: "WHAT DID THE AI DO?", a: "Evaluated every rule deterministically. No discretion, no adjuster, no paperwork." },
      { q: "WHAT DID THE BUSINESS DO?", a: "Its payout obligation crystallised automatically and transparently." },
      { q: "WHAT DID THE RIDER RECEIVE?", a: "A guarantee: no claim form will ever be needed." },
    ];
    case 5: return [
      { q: "WHAT HAPPENED?", a: fmtNum(t.eligible_riders) + " of " + fmtNum(t.affected_riders) + " affected riders are eligible for payout." },
      { q: "WHY DID IT HAPPEN?", a: "Eligibility = ACTIVE weekly policy + home zone in the triggered set + no duplicate claim for the event." },
      { q: "WHAT DID THE AI DO?", a: "Partitioned riders and wrote INELIGIBLE records with reasons for the rest." },
      { q: "WHAT DID THE BUSINESS DO?", a: "Only valid policies created liability — leakage is zero by construction." },
      { q: "WHAT DID THE RIDER RECEIVE?", a: "Arjun's STANDARD policy is ACTIVE — he is eligible." },
    ];
    case 6: return [
      { q: "WHAT HAPPENED?", a: fmtNum(t.approved) + " claims auto-approved; " + fmtNum(t.held) + " held for a human risk manager." },
      { q: "WHY DID IT HAPPEN?", a: "Additive anomaly scoring across 8 signals; scores ≥ 60 are held, never auto-rejected." },
      { q: "WHAT DID THE AI DO?", a: "Recommended. It never accuses — a person makes every borderline decision." },
      { q: "WHAT DID THE BUSINESS DO?", a: "Prevented " + fmtINR(S.baseline ? S.baseline.fraud_prevented : null) + " of fraud so far this season." },
      { q: "WHAT DID THE RIDER RECEIVE?", a: "Honest riders see zero friction; suspicious patterns get a fair human review." },
    ];
    case 7: return [
      { q: "WHAT HAPPENED?", a: fmtINR(t.expected_payout) + " pushed instantly to " + fmtNum(t.approved) + " riders via FPS (SIMULATED)." },
      { q: "WHY DID IT HAPPEN?", a: "Approved claims pay immediately under the parametric policy terms." },
      { q: "WHAT DID THE AI DO?", a: "Executed idempotently — worker:event:policy keys make double payment impossible, even on a rerun." },
      { q: "WHAT DID THE BUSINESS DO?", a: "Settled thousands of claims in one transaction, fully audit-logged." },
      { q: "WHAT DID THE RIDER RECEIVE?", a: (ri.payment_label || "HK$397 credited to FPS — DEMO / SIMULATED") + "." },
    ];
    case 8: return [
      { q: "WHAT HAPPENED?", a: "The week's loss ratio moved to " + fmtPct(t.loss_ratio_after) + " after the event." },
      { q: "WHY DID IT HAPPEN?", a: fmtINR(t.expected_payout) + " of claims was booked against the week's collected premiums." },
      { q: "WHAT DID THE AI DO?", a: "Every rupee is reconciled and written to the append-only audit trail." },
      { q: "WHAT DID THE BUSINESS DO?", a: "Stayed within its priced risk tolerance — this is a planned-for cost, not a surprise." },
      { q: "WHAT DID THE RIDER RECEIVE?", a: "—" },
    ];
    default: return [
      { q: "WHAT HAPPENED?", a: "The business runs at a " + fmtPct(v.loss_ratio) + " loss ratio with " + fmtINR(v.gross_contribution) + " weekly gross contribution." },
      { q: "WHY DID IT HAPPEN?", a: "Premium = expected loss + operating cost + fraud reserve + risk margin." },
      { q: "WHAT DID THE AI DO?", a: "Kept pricing, risk and fraud coherent — the same assumptions drive every engine." },
      { q: "WHAT DID THE BUSINESS DO?", a: "Bought predictable financial exposure and a workforce that stays on the road." },
      { q: "WHAT DID THE RIDER RECEIVE?", a: "Dignity: income protection that costs less than a milk tea a day." },
    ];
  }
}

function topFactorsText(a) {
  const f = Array.isArray(a.risk_factors) ? a.risk_factors.slice(0, 3) : [];
  if (!f.length) return "Rainfall, flood probability and zone history dominate the score.";
  return f.map(function (x) { return x.label + " (+" + x.points + ")"; }).join(", ") + " dominate the score.";
}
