// Live Events — reverse-chronological disruption feed with pipeline recap.

import { api } from "../api.js";
import { fmtINR, fmtNum, fmtTime, timeAgo } from "../format.js";
import {
  esc, badge, skeletonPage, renderError, viewHead, emptyState, pill,
} from "../components.js";

export async function render(el) {
  el.innerHTML = skeletonPage("Live Events");
  let data;
  try {
    data = await api.get("/api/events");
  } catch (err) {
    if (!el.isConnected) return;
    renderError(el, err, function () { render(el); });
    return;
  }
  if (!el.isConnected) return;
  build(el, data);
}

function build(el, data) {
  const events = Array.isArray(data.events) ? data.events : [];

  el.innerHTML =
    viewHead(
      "Live Events",
      "Parametric disruptions processed by the platform " + badge("SIMULATED"),
      '<a class="btn btn-accent btn-lg" href="#/simulation">⚡ SIMULATE DISRUPTION</a>'
    ) +
    '<div class="events-list" id="events-list"></div>';

  const list = el.querySelector("#events-list");
  if (!events.length) {
    list.innerHTML = emptyState(
      "🌤",
      "No events yet",
      "The platform is watching all 10 zones. Run a simulated disruption to see the full parametric pipeline execute end-to-end.",
      '<a class="btn btn-accent" href="#/simulation">▶ Run your first simulation</a>'
    );
    return;
  }

  list.innerHTML = events.map(function (ev, i) { return eventCard(ev, i); }).join("");
  Array.prototype.forEach.call(list.querySelectorAll(".event-card-head"), function (head) {
    head.addEventListener("click", function () {
      const card = head.closest(".event-card");
      const body = card.querySelector(".event-card-body");
      const willOpen = body.hidden;
      body.hidden = !willOpen;
      card.classList.toggle("open", willOpen);
      if (willOpen && !body.getAttribute("data-loaded")) {
        loadRecap(body, card.getAttribute("data-event-id"));
      }
    });
  });
}

function eventCard(ev, i) {
  const totals = ev.totals || {};
  return (
    '<article class="event-card panel" data-event-id="' + esc(ev.event_id) + '">' +
      '<button class="event-card-head" aria-expanded="false">' +
        '<span class="event-icon">⚡</span>' +
        '<span class="event-main">' +
          '<span class="event-title">' + esc(ev.label) + "</span>" +
          '<span class="event-sub">' + esc(ev.zone_name) + " · " + esc(ev.rainfall_mm) + "mm · " + esc(timeAgo(ev.created_at)) + "</span>" +
        "</span>" +
        pill(ev.event_type, "info") +
        '<span class="event-totals">' +
          '<span class="event-total"><strong>' + esc(fmtNum(totals.affected_riders)) + "</strong> affected</span>" +
          '<span class="event-total"><strong>' + esc(fmtINR(totals.payout_total)) + "</strong> paid</span>" +
        "</span>" +
        '<span class="event-chevron">▾</span>' +
      "</button>" +
      '<div class="event-card-body" hidden>' +
        '<div class="recap-loading">' + "Loading pipeline recap…" + "</div>" +
      "</div>" +
    "</article>"
  );
}

// Pipeline recap: audit trail entries recorded against this event id.
async function loadRecap(body, eventId) {
  body.setAttribute("data-loaded", "1");
  let data;
  try {
    data = await api.get("/api/audit?limit=500");
  } catch (err) {
    body.innerHTML = '<div class="error-msg" style="padding:12px">' + esc(err.detail || "Could not load recap") + "</div>";
    return;
  }
  if (!body.isConnected) return;
  const entries = (Array.isArray(data.entries) ? data.entries : []).filter(function (e) {
    return e.entity_id === eventId;
  });
  entries.sort(function (a, b) { return String(a.created_at).localeCompare(String(b.created_at)); });
  if (!entries.length) {
    body.innerHTML = '<p class="muted-text" style="padding:12px">No recorded pipeline steps for this event.</p>';
    return;
  }
  body.innerHTML =
    '<div class="recap">' +
      entries.map(function (e) {
        return (
          '<div class="recap-step">' +
            '<span class="recap-code">' + codeChip(e.event_code) + "</span>" +
            '<span class="recap-detail">' + esc(summarize(e.event_code, e.detail)) + "</span>" +
            '<span class="recap-time">' + esc(fmtTime(e.created_at)) + "</span>" +
          "</div>"
        );
      }).join("") +
    "</div>";
}

function codeChip(code) {
  const c = String(code || "");
  let tone = "info";
  if (c.indexOf("FRAUD") === 0) tone = "warn";
  else if (c.indexOf("PAYOUT") === 0 || c.indexOf("CLAIM_APPROVED") === 0) tone = "ok";
  else if (c.indexOf("TRIGGER") === 0) tone = "danger";
  return pill(c, tone);
}

function summarize(code, detail) {
  let d = detail;
  if (typeof d === "string") {
    try { d = JSON.parse(d); } catch (e) { return String(detail); }
  }
  if (!d || typeof d !== "object") return "";
  switch (code) {
    case "WEATHER_RECEIVED":
      return "Event " + (d.event_type || "") + " received for " + (d.zone_id || "") +
        " — " + (d.rainfall_mm !== undefined ? d.rainfall_mm + "mm" : "") +
        (d.duration_h !== undefined ? ", " + d.duration_h + "h" : "") +
        " [" + (d.data_source || "SIMULATED") + "]";
    case "RISK_CALCULATED":
      return "Risk engine scored " + (d.zones || "—") + " zones; epicenter score " + (d.epicenter_score !== undefined ? d.epicenter_score : "—") +
        " (" + (d.model_version || "") + ")";
    case "TRIGGER_ACTIVATED":
      return (d.fired || 0) + " trigger(s) fired across affected zones";
    case "WORKER_ELIGIBILITY_CHECKED":
      return (d.eligible || 0) + " eligible of " + (d.affected || 0) + " affected riders (" + (d.ineligible || 0) + " ineligible)";
    case "FRAUD_CHECK_COMPLETED":
      return (d.scored || 0) + " claims scored; " + (d.held || 0) + " held for human review";
    case "CLAIM_APPROVED":
      return (d.approved || 0) + " claims auto-approved under policy terms";
    case "PAYOUT_APPROVED":
    case "PAYOUT_SENT":
      return "HK$" + (d.total !== undefined ? Number(d.total).toLocaleString("en-HK") : "—") + " across " + (d.count || 0) + " payouts" +
        (d.method ? " via " + d.method : "");
    default:
      return Object.keys(d).slice(0, 4).map(function (k) { return k + ": " + d[k]; }).join(" · ");
  }
}
