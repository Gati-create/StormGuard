// Risk Analytics — chart grid + model transparency (model card).

import { api } from "../api.js";
import { fmtPct, fmtINR, fmtNum } from "../format.js";
import {
  esc, badge, skeletonPage, renderError, viewHead, panel, statCard,
} from "../components.js";
import { svgLine, svgBars, svgHBars, svgDonut, C, LEVEL_COLORS } from "../charts.js";

export async function render(el) {
  el.innerHTML = skeletonPage("Risk Analytics");
  let summary, card, insurer;
  try {
    summary = await api.get("/api/analytics/summary");
    card = await api.get("/api/model/card");
    insurer = await api.get("/api/insurer/dashboard");
  } catch (err) {
    if (!el.isConnected) return;
    renderError(el, err, function () { render(el); });
    return;
  }
  if (!el.isConnected) return;
  build(el, summary || {}, card || {}, insurer || {});
}

function build(el, s, card, ins) {
  el.innerHTML =
    viewHead(
      "Risk Analytics",
      "Portfolio risk, model behaviour and transparency " + badge("SIMULATED"),
      '<a class="btn btn-ghost" href="/api/export/payouts.csv" download>⬇ Payouts CSV</a>'
    ) +
    insurerSection(ins) +
    '<div class="chart-grid">' +
      panel("Loss ratio over time", svgLine({
        points: arr(s.loss_ratio_over_time).map(function (p) { return { label: p.week, value: p.value }; }),
        fmt: function (v) { return fmtPct(v, 0); }, color: C.teal,
      }), { headRight: badge("SIMULATED") }) +
      panel("Premium vs claims", svgBars({
        groups: arr(s.premium_vs_claims).map(function (p) { return { label: p.week, values: [p.premium, p.claims] }; }),
        series: [{ name: "Premium", color: C.teal }, { name: "Claims", color: C.orange }],
        fmt: fmtINR,
      }), { headRight: badge("SIMULATED") }) +
      panel("Claims by event", svgHBars({
        rows: arr(s.claims_by_event).map(function (p) { return { label: p.label, value: p.value }; }),
        fmt: fmtINR, color: C.blue,
      }), { headRight: badge("SIMULATED") }) +
      panel("Claims by zone", svgHBars({
        rows: arr(s.claims_by_zone).map(function (p) { return { label: p.label, value: p.value }; }),
        fmt: fmtINR, color: C.violet,
      }), { headRight: badge("SIMULATED") }) +
      panel("Risk distribution", svgDonut({
        rows: arr(s.risk_distribution).map(function (p) {
          return { label: p.label, value: p.value, color: LEVEL_COLORS[String(p.label).toUpperCase()] || C.muted };
        }),
        centerLabel: "RIDERS", fmt: fmtNum,
      }), { headRight: badge("SIMULATED") }) +
      panel("Payout distribution", svgHBars({
        rows: arr(s.payout_distribution).map(function (p) { return { label: p.bucket, value: p.value }; }),
        fmt: fmtNum, color: C.amber,
      }), { headRight: badge("SIMULATED") }) +
    "</div>" +
    panel("Average risk-factor contributions", svgHBars({
      rows: arr(s.risk_factors_avg).map(function (p) { return { label: p.label, value: p.points }; }),
      fmt: function (v) { return "+" + Math.round(v) + " pts"; }, color: C.teal,
    }), { headRight: badge("MOCK DATA") }) +
    howModelWorks(card) +
    modelCardTable(card);
}

function arr(x) { return Array.isArray(x) ? x : []; }

function insurerSection(ins) {
  const k = ins.cards || {};
  const cards =
    '<div class="cards-row">' +
      statCard({ label: "Portfolio size", value: k.portfolio_size, sub: "covered riders", badgeText: "SIMULATED" }) +
      statCard({ label: "Premium", value: k.premium, fmt: "inr", sub: "current underwriting week" }) +
      statCard({ label: "Claims", value: k.claims, fmt: "inr", sub: "week to date" }) +
      statCard({ label: "Loss ratio", value: k.loss_ratio, fmt: "pct", sub: "claims ÷ premiums", tone: Number(k.loss_ratio) > 0.7 ? "danger" : (Number(k.loss_ratio) > 0.5 ? "warn" : "ok") }) +
      statCard({ label: "Risk reserve", value: k.risk_reserve, fmt: "inr", sub: "held against volatility" }) +
      statCard({ label: "Expected loss", value: k.expected_loss, fmt: "inr", sub: "priced into premiums" }) +
      statCard({ label: "Capital exposure", value: k.capital_exposure, fmt: "inr", sub: "max weekly payout liability" }) +
      statCard({ label: "Fraud rate", value: k.fraud_rate, fmt: "pct", sub: "of claims, held for review" }) +
    "</div>";
  const rows = arr(ins.forecast_7d).map(function (f) {
    return "<tr><td>" + esc(f.event_type) + "</td><td>" + fmtPct(f.probability, 0) +
      "</td><td>" + fmtINR(f.expected_payout) + "</td></tr>";
  }).join("");
  const forecast = panel(
    "7-day disruption forecast",
    '<table class="table"><thead><tr><th>Event type</th><th>Probability</th><th>Expected payout</th></tr></thead><tbody>' +
      rows + "</tbody></table>" +
      '<div class="panel-note">Probabilities from the mock forecast feed; expected payout = probability × affected riders × mean payout.</div>',
    { headRight: badge("MOCK DATA") }
  );
  return panel("Insurer / actuarial view", cards, { headRight: badge("SIMULATED") }) + forecast;
}

function howModelWorks(card) {
  const stages = Array.isArray(card.architecture) && card.architecture.length ?
    card.architecture :
    ["INPUTS", "FEATURE ENGINEERING", "RISK MODEL", "EXPLAINABILITY", "TRIGGER ENGINE", "PAYOUT ENGINE"];
  const flow = stages.map(function (st, i) {
    return (i > 0 ? '<span class="flow-arrow">→</span>' : "") +
      '<span class="flow-box">' + esc(st) + "</span>";
  }).join("");
  return panel("How the model works", '<div class="flow">' + flow + "</div>", { headRight: badge("MOCK DATA") });
}

function modelCardTable(card) {
  const rows = [
    ["Purpose", txt(card.purpose)],
    ["Inputs", list(card.inputs)],
    ["Outputs", list(card.outputs)],
    ["Training data status", txt(card.training_data_status || "NOT trained on real insurance data — deterministic demo model")],
    ["Limitations", list(card.limitations)],
    ["Bias sources", list(card.bias_sources)],
    ["Human review points", list(card.human_review_points)],
    ["Demo assumptions", list(card.demo_assumptions)],
  ];
  const body = '<table class="table model-card-table"><tbody>' + rows.map(function (r) {
    return '<tr><th class="model-card-key">' + esc(r[0]) + "</th><td>" + r[1] + "</td></tr>";
  }).join("") + "</tbody></table>";
  return panel("Model card", body, { headRight: badge("MOCK DATA") });
}

function txt(x) {
  return x === undefined || x === null || x === "" ? "—" : esc(x);
}

function list(x) {
  if (!Array.isArray(x)) return txt(x);
  return "<ul class=\"card-list\">" + x.map(function (i) { return "<li>" + esc(i) + "</li>"; }).join("") + "</ul>";
}
