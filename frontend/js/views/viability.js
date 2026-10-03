// Business Viability — the profitability simulator.

import { api } from "../api.js";
import { fmtINR, fmtNum, fmtPct } from "../format.js";
import {
  esc, badge, skeletonPage, renderError, viewHead, panel,
  sliderRow, wireSlider, debounce, infoTip,
} from "../components.js";
import { svgGauge, C } from "../charts.js";

const SHOCKS = [
  { key: "weekly_event_probability", mult: 1.25, label: "Severe weather frequency +25%" },
  { key: "avg_payout", mult: 1.20, label: "Average payout +20%" },
  { key: "platform_subsidy_share", mult: 0.85, label: "Platform subsidy −15%" },
];

export async function render(el) {
  el.innerHTML = skeletonPage("Business Viability");
  let initial, stress, comparison;
  try {
    initial = await api.post("/api/viability", {});
    stress = await api.get("/api/viability/stress");
    comparison = await api.get("/api/protection/comparison");
  } catch (err) {
    if (!el.isConnected) return;
    renderError(el, err, function () { render(el); });
    return;
  }
  if (!el.isConnected) return;
  build(el, initial, stress, comparison);
}

function build(el, initial, stress, comparison) {
  const inputs = Object.assign({}, initial.inputs || {});
  const state = { inputs: inputs, base: initial };

  el.innerHTML =
    viewHead(
      "Business Viability",
      "Can this business make money while protecting riders? Move the levers. " + badge("SIMULATED"),
      null
    ) +
    '<div class="viability-layout">' +
      panel("Assumptions", sliderPanelHtml(inputs), { cls: "vi-sliders" }) +
      '<div class="vi-out">' +
        panel("Weekly unit economics", '<div id="vi-weekly"></div>', { headRight: badge("SIMULATED") }) +
        '<div class="vi-row">' +
          panel("Loss ratio", '<div id="vi-gauge" class="gauge-wrap"></div>') +
          panel("Annual projection", '<div id="vi-annual"></div>') +
        "</div>" +
        '<div id="vi-breakeven"></div>' +
      "</div>" +
    "</div>" +
    panel("Sensitivity — what breaks the model?", '<div id="vi-sens"></div>', { headRight: badge("SIMULATED") }) +
    panel("Stress tests", stressTable(stress), { headRight: badge("SIMULATED") }) +
    beforeAfter(comparison) +
    whyBuy(comparison, initial);

  wireSliders(el, state);
  updateOutputs(el, state, initial);
  runSensitivity(el, state);
}

// ---------------------------------------------------------------------------
// Sliders
// ---------------------------------------------------------------------------

function sliderPanelHtml(inp) {
  return (
    sliderRow({ id: "v-riders", label: "Riders on platform", min: 1000, max: 50000, step: 1, value: inp.riders, fmt: function (v) { return Number(v).toLocaleString("en-HK"); } }) +
    sliderRow({ id: "v-income", label: "Avg weekly income", min: 2200, max: 5800, step: 20, value: inp.avg_weekly_income, fmt: function (v) { return "HK$" + Number(v).toLocaleString("en-HK"); } }) +
    sliderRow({ id: "v-premium", label: "Gross premium / rider / week", min: 40, max: 400, step: 10, value: inp.avg_gross_premium, fmt: function (v) { return "HK$" + v; } }) +
    sliderRow({ id: "v-subsidy", label: "Platform subsidy share", min: 0, max: 100, step: 1, value: Math.round((Number(inp.platform_subsidy_share) || 0) * 100), fmt: function (v) { return v + "%"; } }) +
    sliderRow({ id: "v-prob", label: "Weekly event probability", min: 5, max: 60, step: 1, value: Math.round((Number(inp.weekly_event_probability) || 0) * 100), fmt: function (v) { return v + "%"; }, tip: "P(at least one paid disruption event per rider-week), fleet average." }) +
    sliderRow({ id: "v-payout", label: "Avg payout per claim", min: 80, max: 1000, step: 5, value: inp.avg_payout, fmt: function (v) { return "HK$" + v; } }) +
    sliderRow({ id: "v-opex", label: "Operating cost rate", min: 0, max: 25, step: 1, value: Math.round((Number(inp.operating_cost_rate) || 0) * 100), fmt: function (v) { return v + "% of premium"; } }) +
    sliderRow({ id: "v-fraud", label: "Fraud loss rate", min: 0, max: 10, step: 0.5, value: Math.round((Number(inp.fraud_loss_rate) || 0) * 200) / 2, fmt: function (v) { return v + "% of claims"; }, tip: "Leakage after fraud controls, as a share of expected claims." }) +
    '<p class="muted-text" style="margin-top:10px">Outputs recompute live from the pricing & viability engines.</p>'
  );
}

function wireSliders(el, state) {
  const recompute = debounce(function () { fetchViability(el, state); }, 300);
  function bind(id, fmt, apply) {
    wireSlider(el, id, fmt, function (v) { apply(v); recompute(); });
  }
  bind("v-riders", function (v) { return Number(v).toLocaleString("en-HK"); }, function (v) { state.inputs.riders = v; });
  bind("v-income", function (v) { return "HK$" + Number(v).toLocaleString("en-HK"); }, function (v) { state.inputs.avg_weekly_income = v; });
  bind("v-premium", function (v) { return "HK$" + v; }, function (v) { state.inputs.avg_gross_premium = v; });
  bind("v-subsidy", function (v) { return v + "%"; }, function (v) { state.inputs.platform_subsidy_share = v / 100; });
  bind("v-prob", function (v) { return v + "%"; }, function (v) { state.inputs.weekly_event_probability = v / 100; });
  bind("v-payout", function (v) { return "HK$" + v; }, function (v) { state.inputs.avg_payout = v; });
  bind("v-opex", function (v) { return v + "% of premium"; }, function (v) { state.inputs.operating_cost_rate = v / 100; });
  bind("v-fraud", function (v) { return v + "% of claims"; }, function (v) { state.inputs.fraud_loss_rate = v / 100; });
}

async function fetchViability(el, state) {
  try {
    const data = await api.post("/api/viability", state.inputs);
    if (!el.isConnected) return;
    state.base = data;
    updateOutputs(el, state, data);
    runSensitivity(el, state);
  } catch (err) {
    const w = el.querySelector("#vi-weekly");
    if (w && w.isConnected) w.innerHTML = '<div class="error-msg">' + esc(err.detail || "Compute failed") + "</div>";
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

function updateOutputs(el, state, data) {
  const w = data.weekly || {};
  const a = data.annual || {};
  const ex = data.explain || {};

  const weekly = el.querySelector("#vi-weekly");
  if (weekly && weekly.isConnected) {
    const items = [
      { key: "premium_revenue", label: "Premium revenue", value: w.premium_revenue, tone: "teal" },
      { key: "expected_claims", label: "Expected claims", value: w.expected_claims, tone: "warn" },
      { key: "operating_cost", label: "Operating cost", value: w.operating_cost },
      { key: "fraud_losses", label: "Fraud losses", value: w.fraud_losses },
      { key: "risk_reserve", label: "Risk reserve", value: w.risk_reserve },
      { key: "gross_contribution", label: "Gross contribution", value: w.gross_contribution, tone: Number(w.gross_contribution) >= 0 ? "teal" : "danger" },
    ];
    weekly.innerHTML = '<div class="fin-grid">' + items.map(function (it) {
      return '<div class="fin-cell"><div class="fin-label">' + esc(it.label) + " " + infoTip(ex[it.key] || "") + "</div>" +
        '<div class="fin-value' + (it.tone ? " text-" + it.tone : "") + '">' + esc(fmtINR(it.value)) + "</div></div>";
    }).join("") + "</div>";
  }

  const gauge = el.querySelector("#vi-gauge");
  if (gauge && gauge.isConnected) {
    gauge.innerHTML = svgGauge({
      value: (Number(w.loss_ratio) || 0) * 100, max: 120,
      display: fmtPct(w.loss_ratio),
      label: "CLAIMS ÷ PREMIUM", sub: "weekly",
      thresholds: [{ upto: 0.42, color: C.green }, { upto: 0.58, color: C.amber }, { upto: 1, color: C.red }],
    }) + '<p class="muted-text center">' + infoTip(ex.expected_claims || "") + " claims " + esc(fmtINR(w.expected_claims)) +
      " vs premium " + esc(fmtINR(w.premium_revenue)) + "</p>";
  }

  const annual = el.querySelector("#vi-annual");
  if (annual && annual.isConnected) {
    const rows = [
      ["Premium revenue", a.premium_revenue],
      ["Expected claims", a.expected_claims],
      ["Operating cost", a.operating_cost],
      ["Fraud losses", a.fraud_losses],
      ["Risk reserve", a.risk_reserve],
      ["Contribution", a.contribution],
    ];
    annual.innerHTML = '<div class="annual-list">' + rows.map(function (r) {
      const neg = Number(r[1]) < 0;
      return '<div class="annual-row"><span>' + esc(r[0]) + '</span><strong class="' + (neg ? "text-danger" : "") + '">' + esc(fmtINR(r[1])) + "</strong></div>";
    }).join("") + "</div>";
  }

  const be = el.querySelector("#vi-breakeven");
  if (be && be.isConnected) {
    be.innerHTML = data.break_even_riders ?
      '<div class="breakeven-callout">Break-even at <strong>' + esc(fmtNum(data.break_even_riders)) + "</strong> riders " +
        infoTip(ex.break_even_riders || "") +
        ' — the fleet of ' + esc(fmtNum((state.inputs || {}).riders)) + " is " +
        (Number(state.inputs.riders) >= Number(data.break_even_riders) ?
          '<span class="text-ok">above break-even ✓</span>' : '<span class="text-danger">below break-even</span>') +
        "</div>" :
      '<div class="breakeven-callout text-danger">Per-rider contribution is negative — no rider count breaks even with these assumptions.</div>';
  }
}

async function runSensitivity(el, state) {
  const target = el.querySelector("#vi-sens");
  if (!target) return;
  try {
    const data = await api.post("/api/viability/sensitivity", { base: state.inputs, shocks: SHOCKS });
    if (!target.isConnected) return;
    renderSensitivity(target, state.base, data);
  } catch (err) {
    if (target.isConnected) target.innerHTML = '<div class="error-msg">' + esc(err.detail || "Sensitivity failed") + "</div>";
  }
}

function renderSensitivity(target, base, data) {
  const baseWeekly = (base && base.weekly) || {};
  const baseAnnual = (base && base.annual) || {};
  const baseBE = base ? base.break_even_riders : null;
  const rows = (data.results || []).map(function (r) {
    return {
      label: r.label,
      loss: r.loss_ratio,
      dLoss: (Number(r.loss_ratio) || 0) - (Number(baseWeekly.loss_ratio) || 0),
      annual: r.annual_contribution,
      dAnnual: (Number(r.annual_contribution) || 0) - (Number(baseAnnual.contribution) || 0),
      be: r.break_even_riders,
      dBe: baseBE && r.break_even_riders ? r.break_even_riders - baseBE : null,
    };
  });
  target.innerHTML =
    '<div class="table-wrap"><table class="table"><thead><tr>' +
    "<th>Shock</th><th class=\"num\">Loss ratio</th><th class=\"num\">Δ</th><th class=\"num\">Annual contribution</th><th class=\"num\">Δ</th><th class=\"num\">Break-even riders</th>" +
    "</tr></thead><tbody>" +
    rows.map(function (r) {
      return "<tr><td>" + esc(r.label) + "</td>" +
        '<td class="num">' + esc(fmtPct(r.loss)) + "</td>" +
        '<td class="num">' + delta(fmtPct(r.dLoss, 1), r.dLoss > 0, true) + "</td>" +
        '<td class="num">' + esc(fmtINR(r.annual)) + "</td>" +
        '<td class="num">' + delta(fmtINR(Math.abs(r.dAnnual)), r.dAnnual < 0, true) + "</td>" +
        '<td class="num">' + (r.be ? esc(fmtNum(r.be)) + (r.dBe ? " (+" + esc(fmtNum(r.dBe)) + ")" : "") : "—") + "</td></tr>";
    }).join("") +
    "</tbody></table></div>";
}

function delta(text, bad, showSign) {
  const cls = bad ? "delta-bad" : "delta-good";
  const sign = showSign && bad ? "▲ " : (showSign ? "▼ " : "");
  return '<span class="' + cls + '">' + sign + esc(text) + "</span>";
}

// ---------------------------------------------------------------------------
// Stress tests / before-after / why buy
// ---------------------------------------------------------------------------

function stressTable(stress) {
  const scenarios = (stress && stress.scenarios) || [];
  if (!scenarios.length) return '<p class="muted-text">No stress scenarios available.</p>';
  return '<div class="table-wrap"><table class="table"><thead><tr>' +
    "<th>Scenario</th><th class=\"num\">Premium</th><th class=\"num\">Expected claims</th><th class=\"num\">Simulated claims</th>" +
    "<th class=\"num\">Loss ratio</th><th class=\"num\">Operating cost</th><th class=\"num\">Fraud loss</th><th class=\"num\">Reserve</th><th class=\"num\">Contribution</th>" +
    "</tr></thead><tbody>" +
    scenarios.map(function (s) {
      const neg = Number(s.contribution_margin) < 0;
      return "<tr><td>" + esc(s.name) + "</td>" +
        '<td class="num">' + esc(fmtINR(s.premium_revenue)) + "</td>" +
        '<td class="num">' + esc(fmtINR(s.expected_claims)) + "</td>" +
        '<td class="num">' + esc(fmtINR(s.simulated_claims)) + "</td>" +
        '<td class="num">' + esc(fmtPct(s.loss_ratio)) + "</td>" +
        '<td class="num">' + esc(fmtINR(s.operating_cost)) + "</td>" +
        '<td class="num">' + esc(fmtINR(s.fraud_loss)) + "</td>" +
        '<td class="num">' + esc(fmtINR(s.reserve_requirement)) + "</td>" +
        '<td class="num ' + (neg ? "text-danger" : "text-ok") + '">' + esc(fmtINR(s.contribution_margin)) + "</td></tr>";
    }).join("") + "</tbody></table></div>";
}

function beforeAfter(cmp) {
  if (!cmp || !cmp.without || !cmp.with) return "";
  const wo = cmp.without, w = cmp.with;
  const body =
    '<div class="ba-grid">' +
      '<div class="ba-card ba-without">' +
        '<div class="ba-title">' + esc(wo.label || "WITHOUT PROTECTION") + "</div>" +
        baRow("Income loss per rider", fmtINR(wo.income_loss_per_rider)) +
        baRow("Fleet income loss", fmtINR(wo.fleet_income_loss)) +
        baRow("Platform support cost", fmtINR(wo.platform_support_cost)) +
        baRow("Worker protection", fmtINR(wo.worker_protection)) +
      "</div>" +
      '<div class="ba-card ba-with">' +
        '<div class="ba-title">' + esc(w.label || "WITH RIDESHIELD") + "</div>" +
        baRow("Income loss per rider", fmtINR(w.income_loss_per_rider)) +
        baRow("Payout per rider", fmtINR(w.payout_per_rider)) +
        baRow("Net loss per rider", fmtINR(w.net_loss_per_rider)) +
        baRow("Fleet payout", fmtINR(w.fleet_payout)) +
        baRow("Protection cost per rider", fmtINR(w.weekly_protection_cost_per_rider) + "/wk") +
        baRow("Platform subsidy per rider", fmtINR(w.platform_subsidy_per_rider) + "/wk") +
      "</div>" +
    "</div>" +
    '<p class="muted-text" style="margin-top:10px">' + esc(cmp.note || "All values derived from the current scenario assumptions.") +
      (cmp.simulated ? " Based on your latest simulation." : " Based on baseline assumptions (no simulation run yet).") + "</p>";
  return panel("Before / after — the same disruption", body, { headRight: badge("SIMULATED") });
}

function baRow(label, value) {
  return '<div class="ba-row"><span>' + esc(label) + "</span><strong>" + esc(value) + "</strong></div>";
}

function whyBuy(cmp, viability) {
  const w = (cmp && cmp.with) || {};
  const weekly = (viability && viability.weekly) || {};
  const perLoss = Number(w.income_loss_per_rider) || 1;
  const perPayout = Number(w.payout_per_rider) || 0;
  const coverPct = Math.round((perPayout / perLoss) * 100);
  const cards = [
    { t: "WORKER PROTECTION", d: fmtINR(w.payout_per_rider || 0) + " reaches a rider's FPS within minutes of a trigger — no forms, no waiting." },
    { t: "INCOME CONTINUITY", d: "Riders keep ~" + (coverPct || 80) + "% of disrupted income (" + fmtINR(perPayout) + " of " + fmtINR(perLoss) + "), so they stay on the road." },
    { t: "OPERATIONAL RISK MANAGEMENT", d: fmtINR(weekly.expected_claims || 0) + " of weekly claims is absorbed automatically by the parametric pipeline." },
    { t: "PREDICTABLE FINANCIAL EXPOSURE", d: "Loss ratio " + fmtPct(weekly.loss_ratio || 0) + " with a 15% risk reserve — volatility priced in advance." },
  ];
  return panel("Why would a company buy this?",
    '<div class="whybuy-grid">' + cards.map(function (c) {
      return '<div class="whybuy-card"><div class="whybuy-title">' + esc(c.t) + '</div><div class="whybuy-desc">' + esc(c.d) + "</div></div>";
    }).join("") + "</div>");
}
