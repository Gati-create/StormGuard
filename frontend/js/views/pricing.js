// Pricing — plan comparison + interactive quote calculator.

import { api } from "../api.js";
import { fmtINRFull } from "../format.js";
import {
  esc, badge, skeletonPage, renderError, viewHead, panel,
  sliderRow, wireSlider, debounce, infoTip,
} from "../components.js";
import { svgStacked, C } from "../charts.js";
import { setZonesCache } from "../store.js";

const BREAK_COLORS = { expected_loss: C.blue, operating_cost: C.muted, fraud_reserve: C.amber, risk_margin: C.teal };
const BREAK_LABELS = { expected_loss: "Expected loss", operating_cost: "Operating cost", fraud_reserve: "Fraud reserve", risk_margin: "Risk margin" };

export async function render(el) {
  el.innerHTML = skeletonPage("Pricing");
  let zones, plansData;
  try {
    const z = await api.get("/api/fleet/zones");
    zones = (z && z.zones) || [];
    setZonesCache(zones.map(function (x) { return { zone_id: x.zone_id, name: x.name }; }));
    plansData = await api.get("/api/pricing/plans?zone_id=Z-MK&weekly_income=3360&weekly_hours=42");
  } catch (err) {
    if (!el.isConnected) return;
    renderError(el, err, function () { render(el); });
    return;
  }
  if (!el.isConnected) return;
  build(el, zones, plansData);
}

function build(el, zones, plansData) {
  const state = {
    zone_id: (plansData.inputs && plansData.inputs.zone_id) || "Z-MK",
    weekly_income: (plansData.inputs && plansData.inputs.weekly_income) || 3360,
    weekly_hours: (plansData.inputs && plansData.inputs.weekly_hours) || 42,
    plan: "STANDARD",
    subsidy_share: null, // null = platform default (from config)
  };

  const zoneOptions = zones.map(function (z) {
    return '<option value="' + esc(z.zone_id) + '"' + (z.zone_id === state.zone_id ? " selected" : "") + ">" + esc(z.name) + "</option>";
  }).join("");

  el.innerHTML =
    viewHead(
      "Pricing",
      "Actuarial-style micro-premiums, computed from risk — never from personal characteristics " + badge("SIMULATED"),
      null
    ) +
    '<div class="pricing-layout">' +
      '<div class="pricing-left">' +
        panel("Quote calculator",
          '<div class="field">' +
            '<label class="field-label" for="q-zone">Zone</label>' +
            '<select class="select" id="q-zone">' + zoneOptions + "</select>" +
          "</div>" +
          sliderRow({ id: "q-income", label: "Weekly income", min: 2200, max: 5800, step: 20, value: state.weekly_income, fmt: function (v) { return "HK$" + Number(v).toLocaleString("en-HK"); } }) +
          sliderRow({ id: "q-hours", label: "Weekly hours", min: 28, max: 60, step: 1, value: state.weekly_hours, fmt: function (v) { return v + "h"; } }) +
          '<div class="field">' +
            '<label class="field-label" for="q-plan">Plan</label>' +
            '<select class="select" id="q-plan">' +
              '<option value="BASIC">BASIC — 60% coverage</option>' +
              '<option value="STANDARD" selected>STANDARD — 80% coverage</option>' +
              '<option value="PLUS">PLUS — 90% coverage</option>' +
            "</select>" +
          "</div>" +
          sliderRow({ id: "q-subsidy", label: "Platform subsidy", min: 0, max: 100, step: 1, value: 84, fmt: function (v) { return v + "%"; }, tip: "Share of the gross premium paid by the platform. 84% is the fleet default; the worker share is capped at HK$45/week." }) +
          '<div id="quote-result" class="quote-result"></div>'
        ) +
      "</div>" +
      '<div class="pricing-right">' +
        '<div id="plan-cards" class="plan-cards"></div>' +
        '<div class="responsible-note panel">' +
          "<strong>Responsible pricing.</strong> Pricing uses zone, environment, disruption history, " +
          "income exposure and coverage only — never personal characteristics." +
        "</div>" +
      "</div>" +
    "</div>";

  const quoteResult = el.querySelector("#quote-result");
  const planCards = el.querySelector("#plan-cards");

  renderPlanCards(planCards, plansData);

  const runQuote = debounce(function () {
    quoteResult.innerHTML = '<div class="skel skel-block" style="height:180px"></div>';
    api.post("/api/pricing/quote", {
      plan: state.plan,
      zone_id: state.zone_id,
      weekly_income: state.weekly_income,
      weekly_hours: state.weekly_hours,
      subsidy_share: state.subsidy_share,
    }).then(function (q) {
      if (!quoteResult.isConnected) return;
      renderQuote(quoteResult, q);
    }).catch(function (err) {
      if (!quoteResult.isConnected) return;
      quoteResult.innerHTML = '<div class="error-msg">' + esc(err.detail || "Quote failed") + "</div>";
    });
  }, 300);

  const refreshPlans = debounce(function () {
    api.get("/api/pricing/plans?zone_id=" + encodeURIComponent(state.zone_id) +
      "&weekly_income=" + state.weekly_income + "&weekly_hours=" + state.weekly_hours
    ).then(function (d) {
      if (!planCards.isConnected) return;
      renderPlanCards(planCards, d);
    }).catch(function () { /* keep previous cards on transient failure */ });
  }, 400);

  const zoneSel = el.querySelector("#q-zone");
  zoneSel.addEventListener("change", function () {
    state.zone_id = zoneSel.value;
    runQuote(); refreshPlans();
  });
  wireSlider(el, "q-income", function (v) { return "HK$" + Number(v).toLocaleString("en-HK"); }, function (v) {
    state.weekly_income = v; runQuote(); refreshPlans();
  });
  wireSlider(el, "q-hours", function (v) { return v + "h"; }, function (v) {
    state.weekly_hours = v; runQuote(); refreshPlans();
  });
  const planSel = el.querySelector("#q-plan");
  planSel.addEventListener("change", function () { state.plan = planSel.value; runQuote(); });
  wireSlider(el, "q-subsidy", function (v) { return v + "%"; }, function (v) {
    state.subsidy_share = v / 100;
    runQuote();
  });

  runQuote();
}

function renderPlanCards(container, data) {
  const plans = (data && data.plans) || [];
  const explain = (data && data.explain) || "";
  const inputs = (data && data.inputs) || {};
  container.innerHTML = plans.map(function (p) {
    const b = p.breakdown || {};
    const stacked = svgStacked({
      segments: Object.keys(BREAK_LABELS).map(function (k) {
        return { label: BREAK_LABELS[k], value: b[k], color: BREAK_COLORS[k] };
      }),
      fmt: function (v) { return "HK$" + Math.round(v); },
    });
    const gross = Number(p.gross_premium) || 0;
    const worker = Number(p.worker_contribution) || 0;
    const platform = Number(p.platform_subsidy) || 0;
    const workerPct = gross > 0 ? Math.round((worker / gross) * 100) : 0;
    return (
      '<article class="plan-card panel">' +
        '<header class="plan-card-head">' +
          "<div><div class=\"plan-name\">" + esc(p.plan) + "</div>" +
          '<div class="plan-cov">' + Math.round((Number(p.coverage_factor) || 0) * 100) + "% of disrupted income replaced</div></div>" +
          '<div class="plan-price"><span class="plan-price-num">' + esc(fmtINRFull(gross)) + '</span><span class="plan-price-per">/rider/week</span></div>' +
        "</header>" +
        '<div class="plan-caps">' +
          '<span class="chip">Max ' + esc(fmtINRFull(p.max_payout_per_event)) + "/event</span>" +
          '<span class="chip">Limit ' + esc(fmtINRFull(p.weekly_coverage_limit)) + "/week</span>" +
          '<span class="chip">Event probability ' + Math.round((Number(p.weekly_event_probability) || 0) * 100) + "%</span>" +
        "</div>" +
        stacked +
        '<div class="split-bar" title="Platform subsidy vs worker contribution">' +
          '<div class="split-seg split-platform" style="width:' + (100 - workerPct) + '%">Platform ' + esc(fmtINRFull(platform)) + "</div>" +
          '<div class="split-seg split-worker" style="width:' + workerPct + '%"></div>' +
        "</div>" +
        '<div class="plan-cap-note">Worker ' + esc(fmtINRFull(worker)) + '/week — share capped at HK$45/week, affordability first.</div>' +
        '<details class="why"><summary>Why this price? ' + infoTip("Full formula and inputs") + "</summary>" +
          '<p class="why-text">' + esc(explain) + "</p>" +
          '<p class="why-text muted-text">Zone ' + esc(inputs.zone_id || "") + " · weekly income HK$" +
            esc(Number(inputs.weekly_income || 0).toLocaleString("en-HK")) + " · " + esc(inputs.weekly_hours || "") +
            "h · season " + esc(inputs.season || "") + ". Expected payout given an event: " + esc(fmtINRFull(p.expected_payout_given_event)) + ".</p>" +
        "</details>" +
      "</article>"
    );
  }).join("");
}

function renderQuote(container, q) {
  const b = q.breakdown || {};
  const stacked = svgStacked({
    segments: Object.keys(BREAK_LABELS).map(function (k) {
      return { label: BREAK_LABELS[k], value: b[k], color: BREAK_COLORS[k] };
    }),
    fmt: function (v) { return "HK$" + Math.round(v); },
  });
  container.innerHTML =
    '<div class="quote-card">' +
      '<div class="quote-head">Live quote ' + badge("USER INPUT") + "</div>" +
      '<div class="quote-main">' +
        "<div><div class=\"quote-big\">" + esc(fmtINRFull(q.worker_contribution)) + "</div>" +
        '<div class="quote-big-label">rider pays / week</div></div>' +
        "<div><div class=\"quote-mid\">" + esc(fmtINRFull(q.platform_subsidy)) + "</div>" +
        '<div class="quote-big-label">platform subsidy / week</div></div>' +
        "<div><div class=\"quote-mid\">" + esc(fmtINRFull(q.gross_premium)) + "</div>" +
        '<div class="quote-big-label">gross premium / week</div></div>' +
      "</div>" +
      stacked +
      '<p class="why-text">' + esc(q.why || "") + "</p>" +
    "</div>";
}
