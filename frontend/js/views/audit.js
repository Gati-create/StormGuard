// Audit Log — every automated decision leaves an audit record.

import { api } from "../api.js";
import { fmtTime } from "../format.js";
import {
  esc, skeletonPage, renderError, viewHead, pill, emptyState,
} from "../components.js";

const CODE_TONES = {
  WEATHER_RECEIVED: "info",
  RISK_CALCULATED: "info",
  TRIGGER_ACTIVATED: "danger",
  WORKER_ELIGIBILITY_CHECKED: "teal",
  FRAUD_CHECK_COMPLETED: "warn",
  FRAUD_HOLD: "warn",
  CLAIM_APPROVED: "ok",
  PAYOUT_APPROVED: "ok",
  PAYOUT_SENT: "ok",
  MANUAL_REVIEW: "info",
  DEMO_RESET: "muted",
  JUDGE_MODE_STARTED: "teal",
};

export async function render(el) {
  el.innerHTML = skeletonPage("Audit Log");
  let data;
  try {
    data = await api.get("/api/audit?limit=500");
  } catch (err) {
    if (!el.isConnected) return;
    renderError(el, err, function () { render(el); });
    return;
  }
  if (!el.isConnected) return;
  build(el, data);
}

function build(el, data) {
  const entries = Array.isArray(data.entries) ? data.entries : [];
  const codes = [];
  entries.forEach(function (e) {
    if (codes.indexOf(e.event_code) < 0) codes.push(e.event_code);
  });
  codes.sort();

  el.innerHTML =
    viewHead(
      "Audit Log",
      "Every automated decision leaves an audit record — append-only, reviewer-attributed",
      '<button class="btn btn-ghost" id="audit-refresh">↻ Refresh</button>'
    ) +
    '<div class="panel"><div class="panel-body">' +
      '<div class="audit-filters">' +
        '<select class="select" id="audit-code"><option value="">All event codes</option>' +
          codes.map(function (c) { return '<option value="' + esc(c) + '">' + esc(c) + "</option>"; }).join("") +
        "</select>" +
        '<input class="select audit-search" id="audit-search" type="search" placeholder="Search entity, detail, code…">' +
        '<span class="muted-chip" id="audit-count"></span>' +
      "</div>" +
      '<div id="audit-table-wrap"></div>' +
    "</div></div>";

  const wrap = el.querySelector("#audit-table-wrap");
  const codeSel = el.querySelector("#audit-code");
  const search = el.querySelector("#audit-search");
  const count = el.querySelector("#audit-count");

  function apply() {
    const code = codeSel.value;
    const q = search.value.trim().toLowerCase();
    const filtered = entries.filter(function (e) {
      if (code && e.event_code !== code) return false;
      if (!q) return true;
      const hay = (e.event_code + " " + e.entity_type + " " + e.entity_id + " " + (e.detail || "")).toLowerCase();
      return hay.indexOf(q) >= 0;
    });
    count.textContent = filtered.length + " of " + entries.length + " records";
    wrap.innerHTML = tableHtml(filtered);
  }

  codeSel.addEventListener("change", apply);
  search.addEventListener("input", apply);
  el.querySelector("#audit-refresh").addEventListener("click", function () { render(el); });
  apply();
}

function tableHtml(entries) {
  if (!entries.length) {
    return emptyState("🧾", "No audit records", "Records appear here as the platform makes decisions — run a simulation or reset the demo.", "");
  }
  return '<div class="table-wrap"><table class="table"><thead><tr>' +
    "<th>Time</th><th>Event code</th><th>Entity</th><th>Summary</th></tr></thead><tbody>" +
    entries.map(function (e) {
      return "<tr><td class=\"muted-cell nowrap\">" + esc(fmtTime(e.created_at)) + "</td>" +
        "<td>" + pill(e.event_code, CODE_TONES[e.event_code] || "info") + "</td>" +
        '<td class="mono nowrap">' + esc(e.entity_type) + ":" + esc(e.entity_id) + "</td>" +
        '<td class="audit-summary">' + esc(summarize(e.event_code, e.detail)) + "</td></tr>";
    }).join("") + "</tbody></table></div>";
}

function summarize(code, detail) {
  let d = detail;
  if (typeof d === "string") {
    try { d = JSON.parse(d); } catch (e) { return String(detail); }
  }
  if (!d || typeof d !== "object") return "";
  switch (code) {
    case "WEATHER_RECEIVED":
      return (d.event_type || "Event") + " in " + (d.zone_id || "—") + " — " +
        (d.rainfall_mm !== undefined ? d.rainfall_mm + "mm" : "") +
        (d.duration_h !== undefined ? ", " + d.duration_h + "h" : "") +
        " [" + (d.data_source || "SIMULATED") + "]";
    case "RISK_CALCULATED":
      return (d.zones || "—") + " zones scored; epicenter " + (d.epicenter_score !== undefined ? d.epicenter_score : "—") +
        " (" + (d.model_version || "") + ")";
    case "TRIGGER_ACTIVATED":
      return (d.fired || 0) + " trigger(s) fired";
    case "WORKER_ELIGIBILITY_CHECKED":
      return (d.eligible || 0) + " eligible / " + (d.affected || 0) + " affected (" + (d.ineligible || 0) + " ineligible)";
    case "FRAUD_CHECK_COMPLETED":
      return (d.scored || 0) + " scored, " + (d.held || 0) + " held";
    case "FRAUD_HOLD":
      return d.message || ((d.held || 0) + " claim(s) held for human review");
    case "CLAIM_APPROVED":
      return (d.approved || 0) + " claim(s) auto-approved";
    case "PAYOUT_APPROVED":
    case "PAYOUT_SENT":
      return "HK$" + (d.total !== undefined ? Number(d.total).toLocaleString("en-HK") : (d.amount !== undefined ? Number(d.amount).toLocaleString("en-HK") : "—")) +
        (d.count !== undefined ? " across " + d.count + " payout(s)" : "") +
        (d.method ? " via " + d.method : "") +
        (d.reference ? " (ref " + d.reference + ")" : "") +
        (d.reviewer ? " by " + d.reviewer : "");
    case "MANUAL_REVIEW":
      return "Decision " + (d.decision || "—") + " by " + (d.reviewer || "—");
    case "DEMO_RESET":
      return "Demo restored to deterministic baseline";
    case "JUDGE_MODE_STARTED":
      return "Judge mode started (" + (d.script_steps || "—") + " script steps)";
    default:
      return Object.keys(d).slice(0, 5).map(function (k) { return k + ": " + d[k]; }).join(" · ");
  }
}
