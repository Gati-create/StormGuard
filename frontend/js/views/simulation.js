// Simulation — the hero view. Configure a disruption, run the 9-stage
// parametric pipeline, watch it execute, inspect the results.

import { api } from "../api.js";
import { fmtINR, fmtINRFull, fmtNum, fmtPct, fmtCompact, fmtHours } from "../format.js";
import {
  esc, badge, skeletonPage, renderError, viewHead, panel, statusPill,
  sliderRow, wireSlider, toggleRow, toastError,
} from "../components.js";
import { renderCityMap, mapLegendHtml } from "../map.js";
import { saveSimulation, getZonesCache } from "../store.js";

const STAGE_ICONS = {
  WEATHER: "🌧", RISK: "🤖", EXPOSURE: "👥", TRIGGER: "⚡", ELIGIBILITY: "✅",
  FRAUD: "🕵️", APPROVAL: "✔", PAYOUT: "💸", FINANCE: "📈",
};
const PRESET_ORDER = ["NORMAL_DAY", "SEVERE_RAIN", "EXTREME_FLOOD", "BLACK_SWAN"];
const PRESET_EMOJI = { NORMAL_DAY: "☀️", SEVERE_RAIN: "🌧", EXTREME_FLOOD: "🌊", BLACK_SWAN: "⬛" };

let timers = [];
let running = false;

export function destroy() {
  timers.forEach(clearTimeout);
  timers = [];
  running = false;
}

function later(fn, ms) {
  const id = setTimeout(fn, ms);
  timers.push(id);
  return id;
}

export async function render(el) {
  destroy();
  el.innerHTML = skeletonPage("Simulation");
  let config, zones;
  try {
    config = await api.get("/api/config");
    if (getZonesCache()) {
      zones = getZonesCache();
    } else {
      const z = await api.get("/api/fleet/zones");
      zones = (z.zones || []).map(function (x) { return { zone_id: x.zone_id, name: x.name }; });
    }
  } catch (err) {
    if (!el.isConnected) return;
    renderError(el, err, function () { render(el); });
    return;
  }
  if (!el.isConnected) return;
  build(el, config, zones);
}

// ---------------------------------------------------------------------------

function build(el, config, zones) {
  const scenarios = config.scenarios || {};
  const state = {
    scenarioKey: "EXTREME_FLOOD",
    zoneId: ((scenarios.EXTREME_FLOOD || {}).zone_id) || "Z-MK",
    dirty: false,
  };
  const cur = function () { return scenarios[state.scenarioKey] || { weather: {} }; };
  const w0 = function () { return cur().weather || {}; };

  const zoneOptions = zones.map(function (z) {
    return '<option value="' + esc(z.zone_id) + '"' + (z.zone_id === state.zoneId ? " selected" : "") + ">" + esc(z.name) + "</option>";
  }).join("");

  el.innerHTML =
    viewHead(
      "Simulation",
      "Compose a disruption and watch the parametric pipeline decide — end to end " + badge("SIMULATED"),
      null
    ) +
    '<div class="sim-layout">' +
      '<div class="sim-controls">' +
        panel("Scenario presets",
          '<div class="preset-grid">' + PRESET_ORDER.map(function (k) {
            const sc = scenarios[k];
            if (!sc) return "";
            return '<button class="preset-card' + (k === state.scenarioKey ? " active" : "") + '" data-preset="' + k + '">' +
              '<span class="preset-emoji">' + (PRESET_EMOJI[k] || "▶") + "</span>" +
              '<span class="preset-label">' + esc(sc.label || k) + "</span>" +
              '<span class="preset-sub">' + esc((sc.weather || {}).rainfall_mm) + "mm · " + esc((sc.weather || {}).duration_h) + "h</span>" +
              "</button>";
          }).join("") + "</div>"
        ) +
        panel("Conditions",
          '<div class="field"><label class="field-label" for="sim-zone">Epicenter zone</label>' +
            '<select class="select" id="sim-zone">' + zoneOptions + "</select></div>" +
          sliderRow({ id: "sim-rain", label: "Rainfall", min: 0, max: 180, step: 1, value: w0().rainfall_mm, fmt: function (v) { return v + " mm"; } }) +
          sliderRow({ id: "sim-flood", label: "Flood probability", min: 0, max: 100, step: 1, value: Math.round((Number(w0().flood_probability) || 0) * 100), fmt: function (v) { return v + "%"; } }) +
          sliderRow({ id: "sim-temp", label: "Temperature", min: 15, max: 48, step: 0.5, value: w0().temperature_c, fmt: function (v) { return v + "°C"; } }) +
          sliderRow({ id: "sim-aqi", label: "Air quality (AQI)", min: 0, max: 500, step: 5, value: w0().aqi, fmt: function (v) { return String(v); } }) +
          sliderRow({ id: "sim-wind", label: "Wind speed", min: 0, max: 110, step: 1, value: w0().wind_speed_kmh, fmt: function (v) { return v + " km/h"; } }) +
          sliderRow({ id: "sim-duration", label: "Duration", min: 0.5, max: 10, step: 0.5, value: w0().duration_h, fmt: function (v) { return v + "h"; } }) +
          sliderRow({ id: "sim-traffic", label: "Traffic disruption", min: 0, max: 100, step: 1, value: Math.round((Number(w0().rainfall_intensity) || 0) / 0.45), fmt: function (v) { return v + "%"; }, tip: "Proxied into rainfall intensity (mm/h) for the risk model — the API's closest accepted signal. Static zone traffic indices drive the traffic risk factor." }) +
          toggleRow({ id: "sim-closure", label: "Zone closure ordered", checked: !!w0().zone_closure }) +
          toggleRow({ id: "sim-outage", label: "Platform outage", checked: (Number(w0().platform_availability_pct) || 100) < 85 })
        ) +
        '<details class="sim-advanced panel"><summary>Advanced overrides</summary><div class="panel-body">' +
          '<div class="field"><label class="field-label" for="sim-riders">Affected riders override <span class="muted-text">(blank = auto)</span></label>' +
            '<input class="select" type="number" min="0" step="1" id="sim-riders" placeholder="auto"></div>' +
          '<div class="field"><label class="field-label" for="sim-coverage">Coverage factor</label>' +
            '<select class="select" id="sim-coverage"><option value="">plan default</option>' +
            '<option value="0.6">0.60 (BASIC)</option><option value="0.8">0.80 (STANDARD)</option>' +
            '<option value="0.9">0.90 (PLUS)</option><option value="1">1.00 (full)</option></select></div>' +
          '<div class="field"><label class="field-label" for="sim-subsidy">Platform subsidy share</label>' +
            '<select class="select" id="sim-subsidy"><option value="">plan default</option>' +
            '<option value="0">0%</option><option value="0.5">50%</option><option value="0.76">76%</option><option value="1">100%</option></select></div>' +
        "</div></details>" +
        '<button class="btn btn-accent btn-run" id="sim-run">RUN SCENARIO ▶</button>' +
      "</div>" +
      '<div class="sim-stage" id="sim-stage">' +
        '<div class="panel sim-idle"><div class="empty-icon">⚡</div>' +
          '<div class="empty-title">Ready when you are</div>' +
          '<p class="empty-msg">Pick a preset (or craft your own conditions) and press RUN SCENARIO. ' +
          "The full pipeline executes on the backend; this stage animates each decision step with the real computed outputs.</p>" +
        "</div>" +
      "</div>" +
    "</div>";

  // -- wiring ---------------------------------------------------------------
  const zoneSel = el.querySelector("#sim-zone");
  zoneSel.addEventListener("change", function () { state.zoneId = zoneSel.value; state.dirty = true; });

  Array.prototype.forEach.call(el.querySelectorAll("[data-preset]"), function (btn) {
    btn.addEventListener("click", function () {
      state.scenarioKey = btn.getAttribute("data-preset");
      state.dirty = false;
      const sc = cur();
      state.zoneId = sc.zone_id || state.zoneId;
      zoneSel.value = state.zoneId;
      Array.prototype.forEach.call(el.querySelectorAll("[data-preset]"), function (b) {
        b.classList.toggle("active", b === btn);
      });
      fillSliders(el, sc.weather || {});
    });
  });

  function markDirty() { state.dirty = true; }
  wireSlider(el, "sim-rain", function (v) { return v + " mm"; }, markDirty);
  wireSlider(el, "sim-flood", function (v) { return v + "%"; }, markDirty);
  wireSlider(el, "sim-temp", function (v) { return v + "°C"; }, markDirty);
  wireSlider(el, "sim-aqi", function (v) { return String(v); }, markDirty);
  wireSlider(el, "sim-wind", function (v) { return v + " km/h"; }, markDirty);
  wireSlider(el, "sim-duration", function (v) { return v + "h"; }, markDirty);
  wireSlider(el, "sim-traffic", function (v) { return v + "%"; }, markDirty);
  el.querySelector("#sim-closure").addEventListener("change", markDirty);
  el.querySelector("#sim-outage").addEventListener("change", markDirty);

  el.querySelector("#sim-run").addEventListener("click", function () { runScenario(el, state); });
}

function fillSliders(el, w) {
  setSlider(el, "sim-rain", w.rainfall_mm, function (v) { return v + " mm"; });
  setSlider(el, "sim-flood", Math.round((Number(w.flood_probability) || 0) * 100), function (v) { return v + "%"; });
  setSlider(el, "sim-temp", w.temperature_c, function (v) { return v + "°C"; });
  setSlider(el, "sim-aqi", w.aqi, function (v) { return String(v); });
  setSlider(el, "sim-wind", w.wind_speed_kmh, function (v) { return v + " km/h"; });
  setSlider(el, "sim-duration", w.duration_h, function (v) { return v + "h"; });
  setSlider(el, "sim-traffic", Math.round((Number(w.rainfall_intensity) || 0) / 0.45), function (v) { return v + "%"; });
  el.querySelector("#sim-closure").checked = !!w.zone_closure;
  el.querySelector("#sim-outage").checked = (Number(w.platform_availability_pct) || 100) < 85;
}

function setSlider(el, id, value, fmt) {
  const input = el.querySelector("#" + id);
  const readout = el.querySelector("#" + id + "-val");
  if (!input || value === undefined || value === null) return;
  input.value = value;
  if (readout) readout.textContent = fmt(Number(value));
}

function sliderVal(el, id) {
  const input = el.querySelector("#" + id);
  return input ? Number(input.value) : 0;
}

// ---------------------------------------------------------------------------
// Run
// ---------------------------------------------------------------------------

async function runScenario(el, state) {
  if (running) return;
  running = true;
  destroy2();
  const stageEl = el.querySelector("#sim-stage");
  const runBtn = el.querySelector("#sim-run");
  runBtn.disabled = true;
  runBtn.innerHTML = '<span class="spinner"></span> RUNNING…';
  stageEl.innerHTML =
    '<div class="panel sim-running"><div class="running-head">' +
    '<span class="spinner"></span> Executing pipeline on the backend…</div></div>';

  // Snapshot fleet state for the before/after delta.
  let preCards = null;
  try {
    const pre = await api.get("/api/fleet/dashboard");
    preCards = pre.cards || null;
  } catch (e) { preCards = null; }

  const body = { zone_id: state.zoneId, scenario_key: state.scenarioKey };
  if (state.dirty) {
    const outage = el.querySelector("#sim-outage").checked;
    body.weather = {
      rainfall_mm: sliderVal(el, "sim-rain"),
      rainfall_intensity: Math.round(sliderVal(el, "sim-traffic") * 0.45 * 10) / 10,
      temperature_c: sliderVal(el, "sim-temp"),
      aqi: sliderVal(el, "sim-aqi"),
      wind_speed_kmh: sliderVal(el, "sim-wind"),
      flood_probability: sliderVal(el, "sim-flood") / 100,
      duration_h: sliderVal(el, "sim-duration"),
      platform_availability_pct: outage ? 82 : 99.5,
      zone_closure: el.querySelector("#sim-closure").checked,
    };
  }
  const overrides = {};
  const ridersOverride = el.querySelector("#sim-riders").value;
  if (ridersOverride !== "") overrides.affected_riders = Math.max(0, parseInt(ridersOverride, 10) || 0);
  const cov = el.querySelector("#sim-coverage").value;
  if (cov !== "") overrides.coverage_factor = Number(cov);
  const sub = el.querySelector("#sim-subsidy").value;
  if (sub !== "") overrides.platform_subsidy_share = Number(sub);
  if (Object.keys(overrides).length) body.overrides = overrides;

  let resp;
  try {
    resp = await api.post("/api/simulate", body);
  } catch (err) {
    running = false;
    runBtn.disabled = false;
    runBtn.textContent = "RUN SCENARIO ▶";
    if (stageEl.isConnected) {
      stageEl.innerHTML = '<div class="error-box panel"><div class="error-icon">⚠</div>' +
        '<div class="error-title">Simulation failed</div>' +
        '<div class="error-msg">' + esc(err.detail || "Unknown error") + "</div></div>";
    }
    toastError(err.detail || "Simulation failed");
    return;
  }
  if (!el.isConnected) { running = false; return; }
  saveSimulation(resp);
  animateStages(el, stageEl, resp, preCards, runBtn);
}

function destroy2() {
  timers.forEach(clearTimeout);
  timers = [];
}

// ---------------------------------------------------------------------------
// Stage animation
// ---------------------------------------------------------------------------

function animateStages(viewEl, stageEl, resp, preCards, runBtn) {
  const stages = Array.isArray(resp.stages) ? resp.stages : [];
  stageEl.innerHTML =
    '<div class="sim-timeline-head">' +
      '<span class="sim-timeline-title">PIPELINE EXECUTION</span>' +
      '<button class="btn btn-ghost btn-sm" id="sim-skip">SKIP ▸</button>' +
    "</div>" +
    '<div class="sim-timeline">' +
      stages.map(function (st, i) {
        return '<div class="stage-card pending" data-stage="' + i + '">' +
          '<div class="stage-marker"><span class="stage-spinner"></span><span class="stage-check">✓</span></div>' +
          '<div class="stage-content">' +
            '<div class="stage-title-row"><span class="stage-icon">' + (STAGE_ICONS[st.key] || "•") + "</span>" +
              '<span class="stage-title">' + esc(st.title || st.key) + "</span>" +
              '<span class="stage-state">QUEUED</span></div>' +
            '<div class="stage-reveal" hidden>' +
              '<div class="stage-summary">' + esc(st.summary || "") + "</div>" +
              metricChips(st.metrics) +
              '<div class="stage-detail">' + esc(st.detail || "") + "</div>" +
            "</div>" +
          "</div>" +
        "</div>";
      }).join("") +
    "</div>" +
    '<div class="sim-results" id="sim-results" hidden></div>';

  const cards = stageEl.querySelectorAll(".stage-card");
  let idx = 0;
  let finished = false;

  function finishAll() {
    if (finished) return;
    finished = true;
    destroy2();
    Array.prototype.forEach.call(cards, function (c) { revealStage(c); });
    showResults(viewEl, stageEl, resp, preCards, runBtn);
  }

  function step() {
    if (finished || !stageEl.isConnected) return;
    if (idx >= cards.length) { finishAll(); return; }
    revealStage(cards[idx]);
    idx += 1;
    later(step, 700 + Math.random() * 500);
  }

  const skipBtn = stageEl.querySelector("#sim-skip");
  skipBtn.addEventListener("click", function () {
    skipBtn.remove();
    finishAll();
  });

  later(step, 450);
}

function revealStage(card) {
  if (!card || !card.isConnected) return;
  card.classList.remove("pending");
  card.classList.add("done");
  const state = card.querySelector(".stage-state");
  if (state) state.textContent = "DONE";
  const reveal = card.querySelector(".stage-reveal");
  if (reveal) reveal.hidden = false;
}

function metricChips(metrics) {
  if (!metrics || typeof metrics !== "object") return "";
  const chips = Object.keys(metrics).slice(0, 6).map(function (k) {
    let v = metrics[k];
    if (typeof v === "number") v = Math.abs(v) >= 1000 ? fmtCompact(v) : (Math.round(v * 100) / 100);
    if (typeof v === "object") v = JSON.stringify(v);
    v = String(v);
    if (v.length > 18) v = v.slice(0, 17) + "…";
    return '<span class="metric-chip"><span class="metric-k">' + esc(k) + '</span><span class="metric-v">' + esc(v) + "</span></span>";
  }).join("");
  return chips ? '<div class="metric-row">' + chips + "</div>" : "";
}

// ---------------------------------------------------------------------------
// Results
// ---------------------------------------------------------------------------

function showResults(viewEl, stageEl, resp, preCards, runBtn) {
  running = false;
  if (runBtn && runBtn.isConnected) {
    runBtn.disabled = false;
    runBtn.textContent = "RUN SCENARIO ▶";
  }
  const results = stageEl.querySelector("#sim-results");
  if (!results || !results.isConnected) return;
  const t = resp.totals || {};
  const noTrigger = !Number(t.affected_riders);
  const triggerStage = (resp.stages || []).filter(function (s) { return s.key === "TRIGGER"; })[0];

  results.hidden = false;
  results.innerHTML =
    '<div class="results-fade">' +
    (noTrigger ?
      '<div class="event-strip calm"><span class="event-strip-icon">🛈</span>' +
        '<span class="event-strip-text"><strong>No parametric trigger satisfied — thresholds not breached.</strong> ' +
        esc((triggerStage && triggerStage.detail) || "The pipeline completed with zero payouts.") + "</span>" + badge("SIMULATED") + "</div>" : "") +

    '<div class="cards-row cards-4">' +
      miniStat("Affected riders", fmtNum(t.affected_riders)) +
      miniStat("Approved claims", fmtNum(t.approved), "ok") +
      miniStat("Held for review", fmtNum(t.held), Number(t.held) ? "warn" : "") +
      miniStat("Income exposure", fmtINR(t.income_exposure)) +
      miniStat("Expected payout", fmtINR(t.expected_payout), "teal") +
      miniStat("Avg payout", fmtINR(t.avg_payout)) +
      miniStat("Platform liability", fmtINR(t.platform_liability)) +
      miniStat("Loss ratio after", fmtPct(t.loss_ratio_after), Number(t.loss_ratio_after) > 0.7 ? "danger" : "") +
    "</div>" +

    '<div class="grid-2">' +
      panel("Post-event zone risk", '<div class="map-wrap">' +
        renderCityMap(resp.zones || [], { epicenterId: (resp.assessment || {}).zone_id }) +
        "</div>" + mapLegendHtml(), { headRight: badge("SIMULATED") }) +
      riderImpactPanel(resp.rider_impact, resp.assessment) +
    "</div>" +

    fleetDeltaPanel(resp.fleet_cards, preCards, t) +

    panel("Sample claims (first 12)", sampleClaimsTable(resp.sample_claims), { headRight: badge("SIMULATED") }) +

    '<div class="sim-post-note">' + badge("SIMULATED") + " Elapsed server-side: " + esc(resp.elapsed_ms || "—") +
      "ms · Event " + esc(resp.event_id || "") + " · Other dashboards now reflect this run.</div>" +
    "</div>";

  results.scrollIntoView({ behavior: "smooth", block: "start" });
}

function miniStat(label, value, tone) {
  return '<div class="stat-card mini' + (tone ? " tone-" + tone : "") + '">' +
    '<div class="stat-label">' + esc(label) + '</div>' +
    '<div class="stat-value-sm">' + esc(value) + "</div></div>";
}

function riderImpactPanel(impact, assessment) {
  let body;
  if (impact) {
    body =
      '<div class="impact-card wide">' +
        '<div class="impact-rider">👤 Rider ' + esc(impact.worker_id || "W-000001") + " (demo rider)</div>" +
        '<div class="impact-row"><span>Estimated income loss</span><strong class="text-danger">' + esc(fmtINRFull(impact.estimated_income_loss)) + "</strong></div>" +
        '<div class="impact-arrow">→</div>' +
        '<div class="impact-row"><span>Protection payout</span><strong class="text-teal">' + esc(fmtINRFull(impact.protection_payout)) + "</strong></div>" +
        '<div class="impact-status-final">' + statusPill(impact.status || "PAID") + "</div>" +
        '<div class="impact-paid">' + esc(impact.payment_label || "") + "</div>" +
      "</div>";
  } else {
    body = '<p class="muted-text">The demo rider (W-000001, Mong Kok) was outside the affected zone set for this run, so no claim was generated.</p>';
  }
  if (assessment) {
    body += '<div class="ai-meta" style="margin-top:12px">' +
      "<span>Epicenter <strong>" + esc(assessment.zone_name || "") + "</strong></span>" +
      "<span>Risk <strong>" + esc(assessment.risk_score) + " " + esc(assessment.risk_level || "") + "</strong></span>" +
      "<span>Expected disruption <strong>" + esc(fmtHours(assessment.expected_disruption_hours)) + "</strong></span></div>";
  }
  return panel("Rider impact", body, { headRight: badge("SIMULATED") });
}

function fleetDeltaPanel(after, before, totals) {
  const a = after || {};
  const b = before || {};
  function deltaRow(label, av, bv, fmt) {
    const d = (Number(av) || 0) - (Number(bv) || 0);
    const dTxt = (d >= 0 ? "+" : "−") + fmt(Math.abs(d));
    return '<div class="fin-cell"><div class="fin-label">' + esc(label) + "</div>" +
      '<div class="fin-value">' + esc(fmt(av)) + "</div>" +
      '<div class="fin-sub">' + esc(fmt(bv)) + " → <strong>" + esc(fmt(av)) + "</strong> (" + esc(dTxt) + ")</div></div>";
  }
  const body = '<div class="fin-grid">' +
    deltaRow("Premium collected", a.premium_collected, b.premium_collected, fmtINR) +
    deltaRow("Claims paid", a.claims_paid, b.claims_paid, fmtINR) +
    deltaRow("Loss ratio", a.loss_ratio, b.loss_ratio, function (v) { return fmtPct(v); }) +
    deltaRow("Fraud prevented", a.fraud_prevented, b.fraud_prevented, fmtINR) +
    '<div class="fin-cell"><div class="fin-label">This event added</div>' +
      '<div class="fin-value text-teal">' + esc(fmtINR(totals.expected_payout)) + "</div>" +
      '<div class="fin-sub">' + esc(fmtNum(totals.approved)) + " paid · " + esc(fmtNum(totals.held)) + " held</div></div>" +
    "</div>";
  return panel("Fleet financial impact", body, { headRight: badge("SIMULATED") });
}

function sampleClaimsTable(list) {
  const rows = (Array.isArray(list) ? list : []).slice(0, 12);
  if (!rows.length) return '<p class="muted-text">No claims generated in this run.</p>';
  return '<div class="table-wrap"><table class="table"><thead><tr>' +
    "<th>Claim</th><th>Worker</th><th class=\"num\">Payout</th><th>Status</th><th class=\"num\">Fraud score</th></tr></thead><tbody>" +
    rows.map(function (c) {
      return "<tr><td class=\"mono\">" + esc(c.claim_id) + "</td><td class=\"mono\">" + esc(c.worker_id) + "</td>" +
        '<td class="num">' + esc(fmtINRFull(c.payout_amount)) + "</td><td>" + statusPill(c.status) + "</td>" +
        '<td class="num">' + esc(c.fraud_score) + "</td></tr>";
    }).join("") + "</tbody></table></div>";
}
