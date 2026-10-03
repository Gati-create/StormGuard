// Shared UI primitives: stat cards, pills, badges, skeletons, modals, toasts,
// sliders, tooltips, count-up animation. Everything returns HTML strings or
// wires behaviour onto existing DOM — no framework, no dependencies.

import { fmtINR, fmtNum, fmtPct } from "./format.js";

// ---------------------------------------------------------------------------
// small DOM helpers
// ---------------------------------------------------------------------------

export function esc(s) {
  return String(s === null || s === undefined ? "" : s).replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
  });
}

// Create a single element from an HTML string.
export function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

export function debounce(fn, ms) {
  let t = null;
  return function () {
    const args = arguments;
    const self = this;
    if (t) clearTimeout(t);
    t = setTimeout(function () { fn.apply(self, args); }, ms);
  };
}

// ---------------------------------------------------------------------------
// badges / pills / chips
// ---------------------------------------------------------------------------

// Data-source badge: badge("SIMULATED") / badge("MOCK DATA") / badge("USER INPUT")
export function badge(text) {
  const key = String(text || "").toUpperCase();
  let cls = "badge-sim";
  if (key.indexOf("MOCK") >= 0) cls = "badge-mock";
  else if (key.indexOf("USER") >= 0) cls = "badge-user";
  return '<span class="ds-badge ' + cls + '">' + esc(text) + "</span>";
}

// tone: ok | warn | danger | info | muted | teal
export function pill(text, tone) {
  return '<span class="pill pill-' + (tone || "muted") + '">' + esc(text) + "</span>";
}

const STATUS_TONE = {
  PAID: "ok", APPROVED: "teal", ACTIVE: "ok", SENT: "ok",
  HELD: "warn", PENDING: "muted", PROCESSING: "info",
  REJECTED: "danger", INELIGIBLE: "muted", INVESTIGATING: "info",
  LOW: "ok", MODERATE: "warn", HIGH: "high", SEVERE: "danger",
};

export function statusPill(status) {
  const s = String(status || "—");
  return pill(s, STATUS_TONE[s.toUpperCase()] || "muted");
}

export function riskPill(score, level) {
  const lvl = String(level || "").toUpperCase();
  const tone = STATUS_TONE[lvl] || "muted";
  const label = (score === null || score === undefined ? "" : score + " · ") + (lvl || "—");
  return pill(label, tone);
}

// ---------------------------------------------------------------------------
// stat cards (with count-up)
// ---------------------------------------------------------------------------

// opts: { label, value, fmt: "inr"|"num"|"pct"|"raw", sub, tone, badgeText, suffix }
export function statCard(opts) {
  const fmt = opts.fmt || "num";
  const v = opts.value === null || opts.value === undefined || isNaN(Number(opts.value)) ? 0 : Number(opts.value);
  const suffix = opts.suffix || "";
  return (
    '<div class="stat-card' + (opts.tone ? " tone-" + opts.tone : "") + '">' +
      '<div class="stat-top">' +
        '<span class="stat-label">' + esc(opts.label) + "</span>" +
        (opts.badgeText ? badge(opts.badgeText) : "") +
      "</div>" +
      '<div class="stat-value">' +
        '<span data-count="' + v + '" data-fmt="' + fmt + '" data-suffix="' + esc(suffix) + '">' +
          formatBy(fmt, v) + esc(suffix) +
        "</span>" +
      "</div>" +
      (opts.sub ? '<div class="stat-sub">' + esc(opts.sub) + "</div>" : "") +
    "</div>"
  );
}

function formatBy(fmt, v) {
  if (fmt === "inr") return fmtINR(v);
  if (fmt === "pct") return fmtPct(v);
  if (fmt === "raw") return String(Math.round(v));
  return fmtNum(v);
}

// Animate every [data-count] element under root from 0 → target (600ms, ease-out).
export function animateCounters(root, duration) {
  const dur = duration || 600;
  const nodes = root.querySelectorAll("[data-count]");
  Array.prototype.forEach.call(nodes, function (node) {
    const target = Number(node.getAttribute("data-count")) || 0;
    const fmt = node.getAttribute("data-fmt") || "num";
    const suffix = node.getAttribute("data-suffix") || "";
    const t0 = performance.now();
    function frame(t) {
      if (!node.isConnected) return;
      const p = Math.min(1, (t - t0) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      node.textContent = formatBy(fmt, target * eased) + suffix;
      if (p < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  });
}

// ---------------------------------------------------------------------------
// skeletons / errors / empty states
// ---------------------------------------------------------------------------

export function skeletonPage(title) {
  return (
    '<div class="view-head"><div><h1 class="view-title">' + esc(title) + "</h1>" +
    '<div class="skel skel-line" style="width:220px"></div></div></div>' +
    '<div class="cards-row">' +
      '<div class="skel skel-card"></div><div class="skel skel-card"></div>' +
      '<div class="skel skel-card"></div><div class="skel skel-card"></div>' +
      '<div class="skel skel-card"></div>' +
    "</div>" +
    '<div class="skel skel-block"></div>'
  );
}

export function renderError(container, err, retryFn) {
  container.innerHTML =
    '<div class="error-box panel">' +
      '<div class="error-icon">⚠</div>' +
      '<div class="error-title">Couldn\'t load this view</div>' +
      '<div class="error-msg">' + esc(err && err.detail ? err.detail : (err && err.message) || "Unknown error") + "</div>" +
      '<button class="btn btn-accent" data-retry>Retry</button>' +
    "</div>";
  const btn = container.querySelector("[data-retry]");
  if (btn && retryFn) btn.addEventListener("click", retryFn);
}

export function emptyState(icon, title, msg, ctaHtml) {
  return (
    '<div class="empty-box panel">' +
      '<div class="empty-icon">' + esc(icon) + "</div>" +
      '<div class="empty-title">' + esc(title) + "</div>" +
      '<div class="empty-msg">' + esc(msg) + "</div>" +
      (ctaHtml || "") +
    "</div>"
  );
}

// ---------------------------------------------------------------------------
// toasts
// ---------------------------------------------------------------------------

export function toast(msg, type) {
  const root = document.getElementById("toast-root");
  if (!root) return;
  const t = type || "info";
  const node = el(
    '<div class="toast toast-' + t + '">' +
      '<span class="toast-dot"></span><span class="toast-msg">' + esc(msg) + "</span>" +
    "</div>"
  );
  root.appendChild(node);
  requestAnimationFrame(function () { node.classList.add("show"); });
  setTimeout(function () {
    node.classList.remove("show");
    setTimeout(function () { if (node.isConnected) node.remove(); }, 250);
  }, 3800);
}

export function toastSuccess(m) { toast(m, "success"); }
export function toastError(m) { toast(m, "error"); }
export function toastInfo(m) { toast(m, "info"); }

// ---------------------------------------------------------------------------
// modal
// ---------------------------------------------------------------------------

export function openModal(contentHtml, opts) {
  const root = document.getElementById("modal-root");
  if (!root) return { close: function () {}, body: null };
  const wide = opts && opts.wide;
  const overlay = el(
    '<div class="modal-overlay">' +
      '<div class="modal-card' + (wide ? " modal-wide" : "") + '" role="dialog" aria-modal="true">' +
        '<button class="modal-x" aria-label="Close">×</button>' +
        '<div class="modal-body"></div>' +
      "</div>" +
    "</div>"
  );
  const body = overlay.querySelector(".modal-body");
  if (typeof contentHtml === "string") body.innerHTML = contentHtml;
  else if (contentHtml) body.appendChild(contentHtml);

  function close() {
    overlay.classList.remove("show");
    document.removeEventListener("keydown", onKey);
    setTimeout(function () { if (overlay.isConnected) overlay.remove(); }, 200);
  }
  function onKey(e) { if (e.key === "Escape") close(); }
  overlay.addEventListener("mousedown", function (e) { if (e.target === overlay) close(); });
  overlay.querySelector(".modal-x").addEventListener("click", close);
  document.addEventListener("keydown", onKey);
  root.appendChild(overlay);
  requestAnimationFrame(function () { overlay.classList.add("show"); });
  return { close: close, body: body };
}

// ---------------------------------------------------------------------------
// sliders / toggles / info tooltips
// ---------------------------------------------------------------------------

// sliderRow({ id, label, min, max, step, value, fmt, tip })
// fmt is a function applied to the raw value for the readout.
export function sliderRow(opts) {
  const fmt = opts.fmt || function (v) { return v; };
  return (
    '<div class="slider-row">' +
      '<div class="slider-head">' +
        '<label class="slider-label" for="' + esc(opts.id) + '">' + esc(opts.label) +
          (opts.tip ? infoTip(opts.tip) : "") +
        "</label>" +
        '<span class="slider-val" id="' + esc(opts.id) + '-val">' + esc(fmt(opts.value)) + "</span>" +
      "</div>" +
      '<input type="range" class="slider" id="' + esc(opts.id) + '"' +
        ' min="' + opts.min + '" max="' + opts.max + '" step="' + (opts.step || 1) + '"' +
        ' value="' + opts.value + '">' +
    "</div>"
  );
}

// Wire a slider created by sliderRow: keeps readout in sync, calls onChange(rawValue).
export function wireSlider(root, id, fmt, onChange) {
  const input = root.querySelector("#" + CSS.escape(id));
  const readout = root.querySelector("#" + CSS.escape(id) + "-val");
  if (!input) return null;
  const format = fmt || function (v) { return v; };
  function sync() { if (readout) readout.textContent = format(Number(input.value)); }
  input.addEventListener("input", function () {
    sync();
    if (onChange) onChange(Number(input.value));
  });
  sync();
  return input;
}

export function toggleRow(opts) {
  return (
    '<label class="toggle-row" for="' + esc(opts.id) + '">' +
      '<span class="toggle-text">' + esc(opts.label) + (opts.tip ? infoTip(opts.tip) : "") + "</span>" +
      '<span class="toggle">' +
        '<input type="checkbox" id="' + esc(opts.id) + '"' + (opts.checked ? " checked" : "") + ">" +
        '<span class="toggle-track"><span class="toggle-thumb"></span></span>' +
      "</span>" +
    "</label>"
  );
}

// Pure-CSS tooltip: <span class="tip" data-tip="...">ⓘ</span>
export function infoTip(text) {
  return '<span class="tip" data-tip="' + esc(text) + '">ⓘ</span>';
}

export function spinner(label) {
  return '<span class="spinner" aria-hidden="true"></span>' + (label ? '<span class="spinner-label">' + esc(label) + "</span>" : "");
}

// ---------------------------------------------------------------------------
// layout helpers
// ---------------------------------------------------------------------------

export function viewHead(title, sub, rightHtml) {
  return (
    '<div class="view-head">' +
      "<div>" +
        '<h1 class="view-title">' + esc(title) + "</h1>" +
        (sub ? '<p class="view-sub">' + sub + "</p>" : "") +
      "</div>" +
      (rightHtml ? '<div class="view-head-right">' + rightHtml + "</div>" : "") +
    "</div>"
  );
}

export function panel(title, bodyHtml, opts) {
  const o = opts || {};
  return (
    '<section class="panel' + (o.cls ? " " + o.cls : "") + '">' +
      (title ?
        '<header class="panel-head"><h2 class="panel-title">' + esc(title) + "</h2>" +
        (o.headRight ? '<div class="panel-head-right">' + o.headRight + "</div>" : "") +
        "</header>" : "") +
      '<div class="panel-body">' + bodyHtml + "</div>" +
    "</section>"
  );
}
