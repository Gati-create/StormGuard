// Claims & Fraud — claims table + human-in-the-loop fraud review queue.

import { api } from "../api.js";
import { fmtINRFull, fmtTime } from "../format.js";
import {
  esc, badge, skeletonPage, renderError, viewHead, panel, statusPill, pill,
  openModal, toastSuccess, toastError, toastInfo, emptyState,
} from "../components.js";
import { svgGauge, C } from "../charts.js";

const FILTERS = ["ALL", "APPROVED", "HELD", "PAID", "REJECTED", "INELIGIBLE"];
let currentFilter = "ALL";

export async function render(el) {
  el.innerHTML = skeletonPage("Claims & Fraud");
  try {
    const claimsData = await api.get("/api/claims?limit=100" + (currentFilter !== "ALL" ? "&status=" + currentFilter : ""));
    const heldData = await api.get("/api/claims?status=HELD&limit=50");
    if (!el.isConnected) return;
    build(el, claimsData, heldData);
    loadQueueDetails(el, heldData);
  } catch (err) {
    if (!el.isConnected) return;
    renderError(el, err, function () { render(el); });
  }
}

function build(el, claimsData, heldData) {
  const claims = (claimsData && claimsData.claims) || [];
  const counts = (claimsData && claimsData.counts) || {};
  const total = Object.keys(counts).reduce(function (s, k) { return s + (counts[k] || 0); }, 0);
  const held = (heldData && heldData.claims) || [];

  el.innerHTML =
    viewHead(
      "Claims & Fraud",
      "Every claim is scored; only suspicious ones wait for a human " + badge("SIMULATED"),
      '<button class="btn btn-danger" id="btn-sim-fraud">🚨 Simulate Suspicious Claim</button>'
    ) +
    '<div class="claims-layout">' +
      panel("Claims", claimsTableHtml(claims, counts, total), { cls: "claims-panel" }) +
      '<div class="queue-col">' +
        panel("Fraud review queue",
          (held.length ? "" : emptyState("✅", "Queue clear", "No claims are currently held for review.", "")) +
          '<div id="queue-list" class="queue-list">' +
            held.slice(0, 10).map(function (c) {
              return '<div class="queue-card panel" data-claim="' + esc(c.claim_id) + '"><div class="skel skel-block" style="height:120px"></div></div>';
            }).join("") +
          "</div>",
          { headRight: held.length ? pill(held.length + " HELD", "warn") : null }) +
        '<div class="responsible-note panel">' +
          "<strong>Responsible automation.</strong> The AI recommends — humans decide. " +
          "A fraud score never auto-accuses or auto-rejects: claims above the hold threshold " +
          "(60) wait for a risk manager, every review is audit-logged, and no single weak " +
          "signal is enough on its own." +
        "</div>" +
      "</div>" +
    "</div>";

  // filter chips
  Array.prototype.forEach.call(el.querySelectorAll(".filter-chip"), function (chip) {
    chip.addEventListener("click", function () {
      currentFilter = chip.getAttribute("data-filter");
      render(el);
    });
  });

  // claim rows → detail modal
  Array.prototype.forEach.call(el.querySelectorAll("tr[data-claim]"), function (row) {
    row.addEventListener("click", function () {
      openClaimDetail(row.getAttribute("data-claim"));
    });
  });

  el.querySelector("#btn-sim-fraud").addEventListener("click", function () { simulateFraud(el); });
}

function claimsTableHtml(claims, counts, total) {
  const chips = FILTERS.map(function (f) {
    const n = f === "ALL" ? total : (counts[f] || 0);
    return '<button class="filter-chip' + (currentFilter === f ? " active" : "") + '" data-filter="' + f + '">' +
      f + ' <span class="chip-count">' + esc(n) + "</span></button>";
  }).join("");

  const rows = claims.map(function (c) {
    return (
      '<tr data-claim="' + esc(c.claim_id) + '" class="clickable">' +
        "<td class=\"mono\">" + esc(c.claim_id) + "</td>" +
        "<td class=\"mono\">" + esc(c.worker_id) + "</td>" +
        "<td>" + esc(c.zone_id) + "</td>" +
        '<td class="num">' + esc(fmtINRFull(c.payout_amount)) + "</td>" +
        '<td class="num">' + fraudCell(c.fraud_score) + "</td>" +
        "<td>" + statusPill(c.status) + "</td>" +
        '<td class="muted-cell">' + esc(fmtTime(c.created_at)) + "</td>" +
      "</tr>"
    );
  }).join("");

  return (
    '<div class="chip-row filter-row">' + chips + "</div>" +
    (claims.length ?
      '<div class="table-wrap"><table class="table">' +
        "<thead><tr><th>Claim</th><th>Worker</th><th>Zone</th><th class=\"num\">Payout</th><th class=\"num\">Fraud</th><th>Status</th><th>Time</th></tr></thead>" +
        "<tbody>" + rows + "</tbody></table></div>" :
      '<p class="muted-text" style="margin-top:10px">No claims match this filter. Run a simulation to generate claims.</p>')
  );
}

function fraudCell(score) {
  const s = Number(score) || 0;
  const cls = s >= 60 ? "text-danger" : (s >= 30 ? "text-warn" : "text-ok");
  return '<span class="' + cls + '">' + esc(s) + "</span>";
}

// ---------------------------------------------------------------------------
// Fraud review queue (detail per held claim)
// ---------------------------------------------------------------------------

async function loadQueueDetails(el, heldData) {
  const held = ((heldData && heldData.claims) || []).slice(0, 10);
  for (let i = 0; i < held.length; i += 1) {
    const c = held[i];
    const cardEl = el.querySelector('.queue-card[data-claim="' + c.claim_id + '"]');
    if (!cardEl || !cardEl.isConnected) return;
    try {
      const d = await api.get("/api/claims/" + encodeURIComponent(c.claim_id));
      if (!cardEl.isConnected) return;
      cardEl.innerHTML = queueCardHtml(d);
      wireQueueCard(cardEl, d, el);
    } catch (err) {
      if (cardEl.isConnected) {
        cardEl.innerHTML = '<div class="error-msg">' + esc(err.detail || "Failed to load claim") + "</div>";
      }
      return;
    }
  }
}

function queueCardHtml(d) {
  const fc = d.fraud_check || {};
  const signals = Array.isArray(fc.signals) ? fc.signals : [];
  const band = fc.risk_band || "—";
  return (
    '<div class="queue-card-head">' +
      "<div><span class=\"mono\">" + esc(d.claim_id) + "</span> · <span class=\"mono\">" + esc(d.worker_id) + "</span></div>" +
      '<div class="queue-amount">' + esc(fmtINRFull(d.payout_amount)) + "</div>" +
    "</div>" +
    '<div class="queue-mid">' +
      svgGauge({
        value: fc.fraud_score || 0, max: 100,
        label: "FRAUD SCORE", sub: "band " + band,
        thresholds: [{ upto: 0.3, color: C.green }, { upto: 0.6, color: C.amber }, { upto: 1, color: C.red }],
      }) +
      '<div class="queue-signals">' +
        (signals.length ? signals.map(function (s) {
          return '<div class="signal-row"><span class="signal-name">' + esc(s.signal) + "</span>" +
            '<span class="signal-pts">+' + esc(s.points) + "</span>" +
            '<div class="signal-detail">' + esc(s.detail || "") + "</div></div>";
        }).join("") : '<p class="muted-text">No signal detail stored.</p>') +
      "</div>" +
    "</div>" +
    '<div class="queue-reco">AI recommendation: ' + pill(fc.action || "HOLD_FOR_REVIEW", "warn") + "</div>" +
    '<div class="queue-actions">' +
      '<button class="btn btn-ok btn-sm" data-decision="APPROVED">Approve</button>' +
      '<button class="btn btn-ghost btn-sm" data-decision="HOLD">Hold</button>' +
      '<button class="btn btn-danger btn-sm" data-decision="REJECTED">Reject</button>' +
      '<button class="btn btn-ghost btn-sm" data-decision="INVESTIGATING">Request investigation</button>' +
    "</div>"
  );
}

function wireQueueCard(cardEl, claim, viewRoot) {
  Array.prototype.forEach.call(cardEl.querySelectorAll("[data-decision]"), function (btn) {
    btn.addEventListener("click", function () {
      const decision = btn.getAttribute("data-decision");
      if (decision === "HOLD") {
        toastInfo("Claim " + claim.claim_id + " remains HELD — no payout will be released until a decision is made.");
        return;
      }
      reviewDecision(claim.claim_id, decision, viewRoot);
    });
  });
}

async function reviewDecision(claimId, decision, viewRoot) {
  try {
    const updated = await api.post("/api/claims/" + encodeURIComponent(claimId) + "/review", {
      decision: decision, reviewer: "Risk Manager",
    });
    if (decision === "APPROVED") {
      toastSuccess("Payout released — idempotency key " + (updated.idempotency_key || claimId));
    } else if (decision === "REJECTED") {
      toastSuccess("Claim " + claimId + " rejected — reserved funds released.");
    } else {
      toastInfo("Claim " + claimId + " moved to INVESTIGATING.");
    }
  } catch (err) {
    toastError(err.detail || "Review failed");
  }
  if (viewRoot.isConnected) render(viewRoot);
}

// ---------------------------------------------------------------------------
// Claim detail modal
// ---------------------------------------------------------------------------

async function openClaimDetail(claimId) {
  const m = openModal('<div class="skel skel-block" style="height:260px"></div>', { wide: true });
  let d;
  try {
    d = await api.get("/api/claims/" + encodeURIComponent(claimId));
  } catch (err) {
    if (m.body && m.body.isConnected) m.body.innerHTML = '<div class="error-msg">' + esc(err.detail || "Failed") + "</div>";
    return;
  }
  if (!m.body || !m.body.isConnected) return;
  const fc = d.fraud_check || null;
  const signals = fc && Array.isArray(fc.signals) ? fc.signals : [];
  const trail = Array.isArray(d.audit_trail) ? d.audit_trail : [];
  m.body.innerHTML =
    '<div class="modal-title-row"><h3 class="modal-title">Claim ' + esc(d.claim_id) + "</h3>" + statusPill(d.status) + "</div>" +
    '<div class="zone-kv-grid">' +
      kv("Worker", d.worker_id) + kv("Zone", d.zone_id) +
      kv("Income loss", fmtINRFull(d.income_loss)) + kv("Payout", fmtINRFull(d.payout_amount)) +
      kv("Affected hours", d.affected_hours === undefined ? "—" : d.affected_hours + "h") +
      kv("Eligible", d.eligible ? "Yes" : "No" + (d.ineligibility_reason ? " — " + d.ineligibility_reason : "")) +
    "</div>" +
    '<div class="modal-sub">Idempotency key</div><div class="mono small">' + esc(d.idempotency_key || "—") + "</div>" +
    (fc ?
      '<div class="modal-sub">Fraud check</div>' +
      '<div class="fraud-detail">' +
        svgGauge({ value: fc.fraud_score || 0, max: 100, label: "SCORE", sub: "band " + (fc.risk_band || "—"),
          thresholds: [{ upto: 0.3, color: C.green }, { upto: 0.6, color: C.amber }, { upto: 1, color: C.red }] }) +
        "<div>" +
          '<div style="margin-bottom:8px">Action: ' + pill(fc.action || "—", "warn") +
            (fc.review_status ? " · reviewed: " + esc(fc.review_status) + " by " + esc(fc.reviewed_by || "—") : "") + "</div>" +
          (signals.length ? signals.map(function (s) {
            return '<div class="signal-row"><span class="signal-name">' + esc(s.signal) + '</span><span class="signal-pts">+' + esc(s.points) + '</span><div class="signal-detail">' + esc(s.detail || "") + "</div></div>";
          }).join("") : '<p class="muted-text">No anomalous signals.</p>') +
        "</div>" +
      "</div>" : "") +
    (d.payout ?
      '<div class="modal-sub">Payout</div>' +
      '<div class="zone-kv-grid">' + kv("Payout id", d.payout.payout_id) + kv("Amount", fmtINRFull(d.payout.amount)) +
        kv("Method", d.payout.method) + kv("Status", d.payout.status) + "</div>" : "") +
    (trail.length ?
      '<div class="modal-sub">Audit trail</div>' +
      '<div class="trail">' + trail.map(function (t) {
        return '<div class="trail-row"><span class="trail-time">' + esc(fmtTime(t.created_at)) + "</span>" +
          pill(t.event_code, "info") + '<span class="trail-detail">' + esc(trailSummary(t.detail)) + "</span></div>";
      }).join("") + "</div>" : "");
}

function kv(label, value) {
  return '<div class="zone-kv"><div class="zone-kv-label">' + esc(label) + '</div><div class="zone-kv-value">' + esc(value === undefined || value === null ? "—" : value) + "</div></div>";
}

function trailSummary(detail) {
  let d = detail;
  if (typeof d === "string") { try { d = JSON.parse(d); } catch (e) { return String(detail); } }
  if (!d || typeof d !== "object") return "";
  return Object.keys(d).slice(0, 4).map(function (k) { return k + ": " + d[k]; }).join(" · ");
}

// ---------------------------------------------------------------------------
// Simulate a suspicious claim
// ---------------------------------------------------------------------------

async function simulateFraud(viewRoot) {
  const btn = viewRoot.querySelector("#btn-sim-fraud");
  if (btn) { btn.disabled = true; btn.textContent = "Scoring…"; }
  let r;
  try {
    r = await api.post("/api/claims/simulate-fraud", {});
  } catch (err) {
    toastError(err.detail || "Simulation failed");
    if (btn) { btn.disabled = false; btn.textContent = "🚨 Simulate Suspicious Claim"; }
    return;
  }
  if (viewRoot.isConnected) render(viewRoot);
  const signals = Array.isArray(r.signals) ? r.signals : [];
  openModal(
    '<div class="fraud-reveal">' +
      '<div class="fraud-reveal-icon">🚨</div>' +
      '<h3 class="modal-title">Suspicious claim detected</h3>' +
      '<p class="muted-text">Generated claim <span class="mono">' + esc(r.claim_id) + "</span> for worker <span class=\"mono\">" + esc(r.worker_id) + "</span></p>" +
      '<div class="fraud-reveal-score">' + esc(r.fraud_score) + '<span class="fraud-reveal-max">/100 · ' + esc(r.risk_band || "") + "</span></div>" +
      signals.map(function (s) {
        return '<div class="signal-row"><span class="signal-name">' + esc(s.signal) + '</span><span class="signal-pts">+' + esc(s.points) + '</span><div class="signal-detail">' + esc(s.detail || "") + "</div></div>";
      }).join("") +
      '<div class="fraud-reveal-msg">' + esc(r.message || "Payout held. A risk manager must review before any payment.") + "</div>" +
      '<p class="muted-text" style="margin-top:10px">The claim is now waiting in the fraud review queue — Approve, Reject or Request investigation from there.</p>' +
    "</div>"
  );
}
