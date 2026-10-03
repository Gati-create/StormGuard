// Fleet Risk — the B2B operations dashboard.

import { api } from "../api.js";
import { fmtINR, fmtNum, fmtPct, fmtTime } from "../format.js";
import {
  esc, badge, statCard, animateCounters, skeletonPage, renderError,
  viewHead, panel, riskPill, pill,
} from "../components.js";
import { renderCityMap, wireCityMap, mapLegendHtml } from "../map.js";
import { svgDonut, C } from "../charts.js";

export async function render(el) {
  el.innerHTML = skeletonPage("Fleet Risk");
  let data;
  try {
    data = await api.get("/api/fleet/dashboard");
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
  const fin = data.financials || {};
  const zones = Array.isArray(data.map_zones) ? data.map_zones : [];
  const plans = data.exposure_by_plan || {};

  el.innerHTML =
    viewHead(
      "Fleet Risk",
      "B2B control centre for the delivery platform " + badge("SIMULATED"),
      '<div class="btn-row">' +
        '<a class="btn btn-ghost" href="/api/export/summary.csv" download>⬇ Summary CSV</a>' +
        '<a class="btn btn-ghost" href="/api/export/risk.csv" download>⬇ Risk CSV</a>' +
      "</div>"
    ) +

    '<div class="cards-row cards-5">' +
      statCard({ label: "Riders protected", value: cards.riders_protected, fmt: "num", sub: "Active weekly policies", badgeText: "SIMULATED" }) +
      statCard({ label: "Premium collected", value: cards.premium_collected, fmt: "inr", sub: "Current underwriting week" }) +
      statCard({ label: "Claims paid", value: cards.claims_paid, fmt: "inr", sub: "Week to date", tone: "teal" }) +
      statCard({ label: "Loss ratio", value: cards.loss_ratio, fmt: "pct", sub: "Claims ÷ premiums", tone: Number(cards.loss_ratio) > 0.7 ? "danger" : (Number(cards.loss_ratio) > 0.5 ? "warn" : "ok") }) +
      statCard({ label: "Fraud prevented", value: cards.fraud_prevented, fmt: "inr", sub: "Held & rejected claims" }) +
    "</div>" +
    '<div class="week-strip">' + esc(data.week_label || "") + "</div>" +

    '<div class="grid-2">' +
      panel("Live risk map", '<div class="map-wrap"></div>' + mapLegendHtml(), { headRight: badge("MOCK DATA") }) +
      panel("Exposure by plan",
        '<div class="donut-wrap">' + svgDonut({
          rows: [
            { label: "BASIC", value: plans.BASIC, color: C.blue },
            { label: "STANDARD", value: plans.STANDARD, color: C.teal },
            { label: "PLUS", value: plans.PLUS, color: C.violet },
          ],
          centerValue: fmtNum((plans.BASIC || 0) + (plans.STANDARD || 0) + (plans.PLUS || 0)),
          centerLabel: "POLICIES",
          fmt: fmtNum,
        }) + "</div>",
        { headRight: badge("SIMULATED") }) +
    "</div>" +

    panel("Financials", financialsGrid(fin, data.projected_next_week_liability), { headRight: badge("SIMULATED") });

  const mapWrap = el.querySelector(".map-wrap");
  mapWrap.innerHTML = renderCityMap(zones, {});
  wireCityMap(mapWrap, function (zoneId) { openZone(el, zoneId); });
  animateCounters(el);

  // A zone requested from another view (e.g. overview map click).
  let pending = null;
  try {
    pending = sessionStorage.getItem("rs_open_zone");
    sessionStorage.removeItem("rs_open_zone");
  } catch (e) { pending = null; }
  if (pending) openZone(el, pending);
}

function financialsGrid(fin, projected) {
  const items = [
    { label: "Platform subsidy", value: fin.platform_subsidy, sub: "Platform share of premiums" },
    { label: "Worker contribution", value: fin.worker_contribution, sub: "Rider-paid share (HK$45 cap)" },
    { label: "Expected claims", value: fin.expected_claims, sub: "Priced expectation" },
    { label: "Actual claims", value: fin.actual_claims, sub: "Paid week to date" },
    { label: "Net risk exposure", value: fin.net_risk_exposure, sub: "Expected − actual" },
    { label: "Projected next-week liability", value: projected, sub: "Model projection" },
  ];
  return '<div class="fin-grid">' + items.map(function (it) {
    return (
      '<div class="fin-cell">' +
        '<div class="fin-label">' + esc(it.label) + "</div>" +
        '<div class="fin-value">' + esc(fmtINR(it.value)) + "</div>" +
        '<div class="fin-sub">' + esc(it.sub) + "</div>" +
      "</div>"
    );
  }).join("") + "</div>";
}

// ---------------------------------------------------------------------------
// Zone slide-over
// ---------------------------------------------------------------------------

async function openZone(viewEl, zoneId) {
  closeZone();
  const ov = document.createElement("div");
  ov.className = "slideover-overlay";
  ov.innerHTML =
    '<aside class="slideover" role="dialog" aria-label="Zone detail">' +
      '<button class="modal-x" data-close aria-label="Close">×</button>' +
      '<div class="slideover-body"><div class="skel skel-block" style="height:220px"></div></div>' +
    "</aside>";
  document.body.appendChild(ov);
  requestAnimationFrame(function () { ov.classList.add("show"); });
  ov.addEventListener("mousedown", function (e) { if (e.target === ov) closeZone(); });
  ov.querySelector("[data-close]").addEventListener("click", closeZone);

  let z;
  try {
    z = await api.get("/api/fleet/zones/" + encodeURIComponent(zoneId));
  } catch (err) {
    ov.querySelector(".slideover-body").innerHTML =
      '<div class="error-box"><div class="error-msg">' + esc(err.detail || "Failed to load zone") + "</div></div>";
    return;
  }
  if (!ov.isConnected) return;

  const factors = Array.isArray(z.top_risk_factors) ? z.top_risk_factors : [];
  const events = Array.isArray(z.recent_events) ? z.recent_events : [];
  const triggers = Array.isArray(z.active_triggers) ? z.active_triggers : [];

  ov.querySelector(".slideover-body").innerHTML =
    '<div class="zone-detail-head">' +
      "<div><div class=\"zone-detail-name\">" + esc(z.name) + "</div>" +
      '<div class="zone-detail-id">' + esc(z.zone_id) + " · " + esc(fmtNum(z.riders)) + " riders</div></div>" +
      riskPill(z.risk_score, z.risk_level) +
    "</div>" +
    '<div class="zone-kv-grid">' +
      kv("Rainfall (latest)", (z.rainfall_mm === undefined ? "—" : z.rainfall_mm + " mm")) +
      kv("Flood probability", z.flood_probability === undefined ? "—" : fmtPct(z.flood_probability, 0)) +
      kv("Affected riders", fmtNum(z.affected_riders)) +
      kv("Income exposure", fmtINR(z.income_exposure)) +
      kv("Expected payout", fmtINR(z.expected_payout)) +
      kv("Base risk", z.base_risk === undefined ? "—" : fmtPct(z.base_risk, 0)) +
    "</div>" +
    '<div class="zone-sub-head">Active triggers</div>' +
    (triggers.length ?
      '<div class="chip-row">' + triggers.map(function (t) { return pill(t, "danger"); }).join("") + "</div>" :
      '<p class="muted-text">None — no parametric threshold breached in this zone.</p>') +
    '<div class="zone-sub-head">Top risk factors</div>' +
    (factors.length ?
      factors.map(function (f) {
        return '<div class="factor-row"><span class="factor-label">' + esc(f.label) + "</span>" +
          '<span class="factor-pts">+' + esc(f.points) + "</span></div>";
      }).join("") :
      '<p class="muted-text">No factor detail available.</p>') +
    '<div class="zone-sub-head">Recent events</div>' +
    (events.length ?
      '<div class="rider-list">' + events.map(function (e) {
        return '<div class="rider-list-row"><div class="rider-list-title">' + esc(e.label) + "</div>" +
          '<span class="rider-list-sub">' + esc(fmtTime(e.created_at)) + "</span></div>";
      }).join("") + "</div>" :
      '<p class="muted-text">No recorded events for this zone.</p>') +
    '<div style="margin-top:14px">' + badge("SIMULATED") + " " + badge("MOCK DATA") + "</div>";
}

function kv(label, value) {
  return '<div class="zone-kv"><div class="zone-kv-label">' + esc(label) + '</div><div class="zone-kv-value">' + esc(value) + "</div></div>";
}

function closeZone() {
  const existing = document.querySelector(".slideover-overlay");
  if (existing) existing.remove();
}
