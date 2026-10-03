// Rider Protection — the rider-facing mobile experience (demo rider W-000001).

import { api } from "../api.js";
import { fmtINRFull, fmtTime } from "../format.js";
import {
  esc, badge, skeletonPage, renderError, viewHead, panel, riskPill, statusPill,
} from "../components.js";
import { svgStacked, C } from "../charts.js";

const DEMO_RIDER = "W-000001";
let timers = [];

export function destroy() {
  timers.forEach(clearTimeout);
  timers = [];
}

function later(fn, ms) {
  const id = setTimeout(fn, ms);
  timers.push(id);
  return id;
}

export async function render(el) {
  destroy();
  el.innerHTML = skeletonPage("Rider Protection");
  let dash, plans;
  try {
    dash = await api.get("/api/riders/" + DEMO_RIDER + "/dashboard");
    plans = await api.get("/api/pricing/plans?zone_id=Z-MK&weekly_income=" +
      encodeURIComponent(dash.weekly_income || 3360) + "&weekly_hours=42");
  } catch (err) {
    if (!el.isConnected) return;
    renderError(el, err, function () { render(el); });
    return;
  }
  if (!el.isConnected) return;
  build(el, dash, plans);
}

function build(el, dash, plans) {
  const worker = dash.worker || {};
  const planName = dash.plan || "STANDARD";
  const plan = ((plans && plans.plans) || []).filter(function (p) { return p.plan === planName; })[0] || null;
  const risk = dash.current_zone_risk || {};
  const ev = dash.latest_event || null;

  el.innerHTML =
    viewHead(
      "Rider Protection",
      "What a delivery rider actually sees " + badge("SIMULATED"),
      '<span class="muted-chip">Deep link: #/rider · rider ' + esc(DEMO_RIDER) + "</span>"
    ) +
    '<div class="rider-layout">' +
      '<div class="phone">' +
        '<div class="phone-notch"></div>' +
        '<div class="phone-screen">' +
          '<div class="phone-app">' +
            '<div class="rider-greet">' +
              "<div><div class=\"rider-hi\">Hello, " + esc(worker.name || "Rider") + "</div>" +
              '<div class="rider-zone">' + esc(worker.zone_name || "") + " · " + esc(worker.worker_id || "") + "</div></div>" +
              riskPill(risk.risk_score, risk.risk_level) +
            "</div>" +
            (ev ? disruptionBanner(ev) : "") +
            '<div class="rider-stats">' +
              riderStat("Weekly income", fmtINRFull(dash.weekly_income)) +
              riderStat("Protected income", fmtINRFull(dash.protected_income)) +
              riderStat("Weekly contribution", fmtINRFull(dash.worker_contribution)) +
              riderStat("Coverage", dash.coverage_status || "—", dash.coverage_status === "ACTIVE" ? "ok" : "warn") +
            "</div>" +
            '<button class="rider-link" data-breakdown>How is my HK$' + esc((plan && plan.worker_contribution) || dash.worker_contribution || "—") + "/week calculated?</button>" +
            '<div class="rider-breakdown" hidden>' + breakdownHtml(plan) + "</div>" +
            (ev ? impactCard(ev) : "") +
            '<div class="rider-section">Recent payouts</div>' +
            payoutsList(dash.recent_payouts) +
            '<div class="rider-section">Coverage history</div>' +
            coverageList(dash.coverage_history) +
          "</div>" +
        "</div>" +
      "</div>" +
      explainerPanel(dash, plan) +
    "</div>";

  const link = el.querySelector("[data-breakdown]");
  const bd = el.querySelector(".rider-breakdown");
  if (link && bd) {
    link.addEventListener("click", function () {
      bd.hidden = !bd.hidden;
      link.classList.toggle("open", !bd.hidden);
    });
  }

  // Animate the payout status chip: PROCESSING → final status (2s).
  if (ev) {
    const chip = el.querySelector(".impact-status");
    if (chip) {
      later(function () {
        if (!chip.isConnected) return;
        chip.classList.remove("is-processing");
        chip.innerHTML = statusPill(ev.status || "PAID");
      }, 2000);
    }
  }
}

function riderStat(label, value, tone) {
  return (
    '<div class="rider-stat">' +
      '<span class="rider-stat-label">' + esc(label) + "</span>" +
      '<span class="rider-stat-value' + (tone === "ok" ? " text-ok" : "") + '">' + esc(value) + "</span>" +
    "</div>"
  );
}

function disruptionBanner(ev) {
  return (
    '<div class="disrupt-banner">' +
      "<strong>Severe disruption detected</strong> — your eligible income protection has been activated. " +
      badge("SIMULATED") +
    "</div>"
  );
}

function impactCard(ev) {
  const payLabel = ev.payment_label || "";
  return (
    '<div class="impact-card">' +
      '<div class="impact-row"><span>Estimated income loss</span><strong class="text-danger">' + esc(fmtINRFull(ev.estimated_income_loss)) + "</strong></div>" +
      '<div class="impact-arrow">→</div>' +
      '<div class="impact-row"><span>Protection payout</span><strong class="text-teal">' + esc(fmtINRFull(ev.protection_payout)) + "</strong></div>" +
      '<div class="impact-status is-processing"><span class="spinner"></span><span class="pill pill-info">PROCESSING</span></div>' +
      '<div class="impact-paid">' + esc(payLabel) + "</div>" +
    "</div>"
  );
}

function breakdownHtml(plan) {
  if (!plan) return '<p class="muted-text">Plan breakdown unavailable.</p>';
  const b = plan.breakdown || {};
  const chart = svgStacked({
    segments: [
      { label: "Expected loss", value: b.expected_loss, color: C.blue },
      { label: "Operating cost", value: b.operating_cost, color: C.muted },
      { label: "Fraud reserve", value: b.fraud_reserve, color: C.amber },
      { label: "Risk margin", value: b.risk_margin, color: C.teal },
    ],
    fmt: function (v) { return "HK$" + Math.round(v); },
  });
  return (
    '<div class="mini-breakdown">' +
      '<div class="mini-break-row"><span>Gross premium</span><strong>' + esc(fmtINRFull(plan.gross_premium)) + "/week</strong></div>" +
      chart +
      '<div class="mini-break-row"><span>Platform pays ' + esc(fmtINRFull(plan.platform_subsidy)) + "</span>" +
      "<span>You pay <strong>" + esc(fmtINRFull(plan.worker_contribution)) + "</strong> (capped at HK$45)</span></div>" +
      '<a href="#/pricing" class="rider-link">Full pricing details →</a>' +
    "</div>"
  );
}

function payoutsList(list) {
  const rows = Array.isArray(list) ? list : [];
  if (!rows.length) return '<p class="muted-text">No payouts yet — they appear here after a covered disruption.</p>';
  return '<div class="rider-list">' + rows.map(function (p) {
    return (
      '<div class="rider-list-row">' +
        "<div><div class=\"rider-list-title\">" + esc(p.event_label || "Payout") + "</div>" +
        '<div class="rider-list-sub">' + esc(fmtTime(p.created_at)) + " · " + esc(p.payout_id) + "</div></div>" +
        '<span class="rider-list-amt text-teal">+' + esc(fmtINRFull(p.amount)) + "</span>" +
      "</div>"
    );
  }).join("") + "</div>";
}

function coverageList(list) {
  const rows = Array.isArray(list) ? list : [];
  if (!rows.length) return '<p class="muted-text">No coverage history available.</p>';
  return '<div class="rider-list">' + rows.map(function (c) {
    return (
      '<div class="rider-list-row">' +
        '<div class="rider-list-title">Week of ' + esc(c.week_start) + "</div>" +
        '<span class="rider-list-amt">' + esc(fmtINRFull(c.premium)) + (c.paid ? ' <span class="text-ok">✓</span>' : "") + "</span>" +
      "</div>"
    );
  }).join("") + "</div>";
}

function explainerPanel(dash, plan) {
  const covPct = plan ? Math.round((Number(plan.coverage_factor) || 0) * 100) + "%" : "—";
  const body =
    '<div class="explain-block">' +
      '<div class="explain-title">What the rider gets</div>' +
      "<ul class=\"tick-list\">" +
        "<li>Income protection when weather or operations disrupt deliveries — no claims paperwork.</li>" +
        "<li>Payouts land directly in the rider's FPS account within minutes of a trigger.</li>" +
        "<li>Weekly micro-premium capped at HK$45 — the platform subsidises the rest.</li>" +
        "<li>Coverage follows objective, published thresholds — never a manager's discretion.</li>" +
      "</ul>" +
    "</div>" +
    '<div class="explain-block">' +
      '<div class="explain-title">Plan details — ' + esc(dash.plan || "STANDARD") + " " + badge("SIMULATED") + "</div>" +
      '<div class="plan-facts">' +
        fact("Coverage factor", covPct, "share of disrupted income replaced") +
        fact("Max payout / event", plan ? fmtINRFull(plan.max_payout_per_event) : "—", "per triggered disruption") +
        fact("Weekly coverage limit", plan ? fmtINRFull(plan.weekly_coverage_limit) : "—", "across all events in a week") +
        fact("Worker contribution", plan ? fmtINRFull(plan.worker_contribution) + "/wk" : "—", "affordability-capped") +
      "</div>" +
    "</div>" +
    '<div class="explain-block">' +
      '<div class="explain-title">Data sources</div>' +
      '<p class="muted-text">Rider identity, FPS handle and payouts are fictional demo records. ' +
      badge("SIMULATED") + " " + badge("MOCK DATA") + " " + badge("USER INPUT") + "</p>" +
    "</div>";
  return panel("Rider explainer", body, { cls: "rider-explainer" });
}

function fact(label, value, sub) {
  return (
    '<div class="plan-fact">' +
      '<div class="plan-fact-label">' + esc(label) + "</div>" +
      '<div class="plan-fact-value">' + esc(value) + "</div>" +
      '<div class="plan-fact-sub">' + esc(sub) + "</div>" +
    "</div>"
  );
}
