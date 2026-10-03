// Overview — the central screen. GET /api/overview.

import { api } from "../api.js";
import { fmtINR, fmtNum, fmtPct, fmtPctInt, fmtHours } from "../format.js";
import {
  esc, badge, statCard, animateCounters, skeletonPage, renderError,
  viewHead, panel, riskPill,
} from "../components.js";
import { renderCityMap, wireCityMap, mapLegendHtml, levelColor } from "../map.js";

export async function render(el) {
  el.innerHTML = skeletonPage("Overview");
  let data;
  try {
    data = await api.get("/api/overview");
  } catch (err) {
    if (!el.isConnected) return;
    renderError(el, err, function () { render(el); });
    return;
  }
  if (!el.isConnected) return;
  build(el, data);
}

function build(el, data) {
  const cards = data.cards || {};
  const ev = data.active_event || null;
  const ai = data.ai_assessment || null;
  const pipe = data.pipeline || {};
  const zones = Array.isArray(data.map_zones) ? data.map_zones : [];

  el.innerHTML =
    viewHead(
      "Overview",
      "Real-time parametric income protection · Hong Kong fleet " + badge("SIMULATED") + " " + badge("MOCK DATA"),
      '<a class="btn btn-accent" href="#/simulation">▶ Run simulation</a>'
    ) +

    '<div class="cards-row cards-5">' +
      statCard({ label: "Riders protected", value: cards.riders, fmt: "num", sub: "Active weekly policies", badgeText: "SIMULATED" }) +
      statCard({ label: "Exposed riders", value: cards.exposed_riders, fmt: "num", sub: ev ? "In active event footprint" : "No active event", tone: ev ? "warn" : "" }) +
      statCard({ label: "Income exposure", value: cards.exposure, fmt: "inr", sub: ev ? "Estimated lost income" : "No active event" }) +
      statCard({ label: "Expected payout", value: cards.payout_total, fmt: "inr", sub: ev ? "Released via FPS (simulated)" : "No active event", tone: ev ? "teal" : "" }) +
      statCard({ label: "Portfolio risk", value: cards.portfolio_risk, fmt: "raw", suffix: "/100", sub: "Fleet-weighted zone risk", tone: riskTone(cards.portfolio_risk) }) +
    "</div>" +

    '<div class="grid-2">' +
      panel("Live risk map", '<div class="map-wrap"></div>' + mapLegendHtml(), { headRight: badge("MOCK DATA") }) +
      aiPanel(ai) +
    "</div>" +

    eventStrip(ev, cards) +
    pipelineStrip(pipe);

  const mapWrap = el.querySelector(".map-wrap");
  mapWrap.innerHTML = renderCityMap(zones, { epicenterId: ev ? evZoneId(zones) : null });
  wireCityMap(mapWrap, function (zoneId) {
    try { sessionStorage.setItem("rs_open_zone", zoneId); } catch (e) { /* ignore */ }
    location.hash = "#/fleet";
  });
  animateCounters(el);
}

function evZoneId(zones) {
  let worst = null;
  zones.forEach(function (z) {
    if (z.active_triggers && z.active_triggers.length) {
      if (!worst || (z.risk_score || 0) > (worst.risk_score || 0)) worst = z;
    }
  });
  return worst ? worst.zone_id : null;
}

function riskTone(score) {
  const s = Number(score) || 0;
  if (s >= 75) return "danger";
  if (s >= 50) return "warn";
  return "ok";
}

function aiPanel(ai) {
  if (!ai) {
    return panel("AI risk assessment",
      '<p class="muted-text">No assessment available yet. Run a simulation to see the model output.</p>',
      { headRight: badge("MOCK DATA"), cls: "ai-panel" });
  }
  const color = levelColor(ai.risk_level);
  const factors = Array.isArray(ai.risk_factors) ? ai.risk_factors.slice() : [];
  factors.sort(function (a, b) { return (Number(b.points) || 0) - (Number(a.points) || 0); });
  const maxPts = Math.max.apply(null, factors.map(function (f) { return Number(f.points) || 0; }).concat([1]));

  const factorRows = factors.map(function (f) {
    const pts = Number(f.points) || 0;
    const w = Math.max(3, Math.round((pts / maxPts) * 100));
    return (
      '<div class="factor-row">' +
        '<span class="factor-label">' + esc(f.label) + "</span>" +
        '<span class="factor-bar"><span class="factor-fill" style="width:' + w + "%;background:" + color + '"></span></span>' +
        '<span class="factor-pts">+' + esc(pts) + "</span>" +
      "</div>"
    );
  }).join("");

  const body =
    '<div class="ai-head">' +
      '<div class="ai-zone">' + esc(ai.zone_name || ai.zone_id || "") + "</div>" +
      riskPill(ai.risk_score, ai.risk_level) +
    "</div>" +
    '<div class="score-bar"><div class="score-fill" style="width:' + Math.min(100, Number(ai.risk_score) || 0) + "%;background:" + color + '"></div>' +
      '<span class="score-num">' + esc(ai.risk_score) + "</span></div>" +
    '<div class="factor-list">' + factorRows + "</div>" +
    '<div class="ai-why">' +
      '<div class="ai-why-title">Why did the risk increase?</div>' +
      '<p class="ai-why-text">' + esc(ai.explanation || "—") + "</p>" +
    "</div>" +
    '<div class="ai-meta">' +
      '<span>Confidence <strong>' + esc(fmtPctInt(ai.confidence_score)) + "</strong></span>" +
      '<span>Model <strong>' + esc(ai.model_version || "—") + "</strong></span>" +
      (ai.expected_disruption_hours ? "<span>Expected disruption <strong>" + esc(fmtHours(ai.expected_disruption_hours)) + "</strong></span>" : "") +
    "</div>" +
    '<div class="ai-note">DEMO MODEL — not trained on real insurance data</div>';

  return panel("AI risk assessment", body, { headRight: badge("MOCK DATA"), cls: "ai-panel" });
}

function eventStrip(ev, cards) {
  if (!ev) {
    return (
      '<div class="event-strip calm">' +
        '<span class="event-strip-icon">☀</span>' +
        '<span class="event-strip-text">No active disruption — conditions normal across all zones.</span>' +
        '<a class="btn btn-ghost btn-sm" href="#/simulation">Simulate a disruption →</a>' +
      "</div>"
    );
  }
  return (
    '<div class="event-strip active">' +
      '<span class="event-strip-icon">⚡</span>' +
      '<span class="event-strip-text"><strong>ACTIVE EVENT:</strong> ' + esc(ev.label) +
        " • " + esc(ev.zone_name) +
        " • " + esc(ev.rainfall_mm) + "mm" +
        " • " + esc(fmtPct(ev.flood_probability, 0)) + " flood probability</span>" +
      '<span class="event-strip-stats">' +
        esc(fmtNum(cards.exposed_riders)) + " riders · " + esc(fmtINR(cards.payout_total)) + " payout" +
      "</span>" +
      badge("SIMULATED") +
    "</div>"
  );
}

function pipelineStrip(pipe) {
  const steps = [
    { key: "trigger", label: "TRIGGER" },
    { key: "eligibility", label: "ELIGIBILITY" },
    { key: "fraud", label: "FRAUD" },
    { key: "payout", label: "PAYOUT" },
  ];
  const anyDone = steps.some(function (s) { return pipe[s.key]; });
  const html = steps.map(function (s, i) {
    const done = !!pipe[s.key];
    return (i > 0 ? '<span class="pipe-sep">→</span>' : "") +
      '<span class="pipe-step ' + (done ? "done" : "pending") + '">' +
        '<span class="pipe-tick">' + (done ? "✓" : "○") + "</span> " + s.label +
      "</span>";
  }).join("");
  return (
    '<div class="pipeline-strip panel">' +
      '<span class="pipeline-title">DECISION PIPELINE</span>' +
      '<span class="pipeline-steps">' + html + "</span>" +
      (anyDone ? badge("SIMULATED") : '<span class="pipeline-hint">ticks appear after a simulation run</span>') +
    "</div>"
  );
}
