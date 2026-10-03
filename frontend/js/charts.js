// Hand-rolled SVG charts. Each function returns an SVG string driven entirely
// by caller data — no libraries, no placeholders.

import { fmtCompact } from "./format.js";
import { esc } from "./components.js";

export const LEVEL_COLORS = {
  LOW: "#22c55e",
  MODERATE: "#eab308",
  HIGH: "#f97316",
  SEVERE: "#ef4444",
};

export const C = {
  teal: "#2dd4bf",
  blue: "#38bdf8",
  green: "#22c55e",
  yellow: "#eab308",
  orange: "#f97316",
  red: "#ef4444",
  amber: "#f59e0b",
  violet: "#a78bfa",
  muted: "#8ba3b8",
  grid: "#1e3a52",
  text: "#e8f0f7",
};

let uidCounter = 0;
function uid(prefix) {
  uidCounter += 1;
  return prefix + "-" + uidCounter;
}

function num(v, fallback) {
  const n = Number(v);
  return isNaN(n) ? (fallback || 0) : n;
}

// ---------------------------------------------------------------------------
// Line chart — svgLine({ points:[{label,value}], fmt, color, height })
// ---------------------------------------------------------------------------
export function svgLine(opts) {
  const points = (opts.points || []).map(function (p) { return { label: String(p.label), value: num(p.value) }; });
  const fmt = opts.fmt || fmtCompact;
  const color = opts.color || C.teal;
  const W = 560, H = opts.height || 220;
  const padL = 46, padR = 14, padT = 16, padB = 26;
  if (!points.length) return emptyChart(W, H, "No data yet");
  const iw = W - padL - padR, ih = H - padT - padB;

  let vmin = Math.min.apply(null, points.map(function (p) { return p.value; }));
  let vmax = Math.max.apply(null, points.map(function (p) { return p.value; }));
  if (vmin === vmax) { vmin = vmin > 0 ? 0 : vmin - 1; vmax = vmax + 1; }
  const span = vmax - vmin;
  vmin = Math.max(0, vmin - span * 0.15);
  vmax = vmax + span * 0.1;
  if (vmax === vmin) vmax = vmin + 1;

  function X(i) { return padL + (points.length === 1 ? iw / 2 : (i / (points.length - 1)) * iw); }
  function Y(v) { return padT + ih - ((v - vmin) / (vmax - vmin)) * ih; }

  let grid = "";
  for (let g = 0; g <= 3; g += 1) {
    const gv = vmin + ((vmax - vmin) * g) / 3;
    const gy = Y(gv);
    grid += '<line x1="' + padL + '" y1="' + gy + '" x2="' + (W - padR) + '" y2="' + gy + '" stroke="' + C.grid + '" stroke-width="0.6"/>' +
      '<text x="' + (padL - 6) + '" y="' + (gy + 3) + '" class="ch-tick" text-anchor="end">' + esc(fmt(gv)) + "</text>";
  }

  let d = "";
  points.forEach(function (p, i) { d += (i === 0 ? "M" : "L") + X(i).toFixed(1) + " " + Y(p.value).toFixed(1) + " "; });
  const gid = uid("lg");
  const area = d + "L" + X(points.length - 1).toFixed(1) + " " + (padT + ih) + " L" + X(0).toFixed(1) + " " + (padT + ih) + " Z";

  let dots = "", labels = "";
  const step = Math.max(1, Math.ceil(points.length / 6));
  points.forEach(function (p, i) {
    dots += '<circle cx="' + X(i).toFixed(1) + '" cy="' + Y(p.value).toFixed(1) + '" r="3" fill="' + color + '">' +
      "<title>" + esc(p.label + ": " + fmt(p.value)) + "</title></circle>";
    if (i % step === 0 || i === points.length - 1) {
      labels += '<text x="' + X(i).toFixed(1) + '" y="' + (H - 8) + '" class="ch-tick" text-anchor="middle">' + esc(p.label) + "</text>";
    }
  });

  const last = points[points.length - 1];
  const chip = '<g><rect x="' + Math.min(W - padR - 74, Math.max(padL, X(points.length - 1) - 66)).toFixed(1) + '" y="' + Math.max(2, Y(last.value) - 26).toFixed(1) + '" width="70" height="18" rx="9" fill="' + color + '" fill-opacity="0.16" stroke="' + color + '" stroke-opacity="0.5"/>' +
    '<text x="' + Math.min(W - padR - 39, Math.max(padL + 35, X(points.length - 1) - 31)).toFixed(1) + '" y="' + (Math.max(2, Y(last.value) - 26) + 13).toFixed(1) + '" class="ch-chip" text-anchor="middle">' + esc(fmt(last.value)) + "</text></g>";

  return '<svg viewBox="0 0 ' + W + " " + H + '" class="chart" role="img">' +
    "<defs><linearGradient id=\"" + gid + '" x1="0" y1="0" x2="0" y2="1">' +
    '<stop offset="0%" stop-color="' + color + '" stop-opacity="0.30"/>' +
    '<stop offset="100%" stop-color="' + color + '" stop-opacity="0.02"/></linearGradient></defs>' +
    grid +
    '<path d="' + area + '" fill="url(#' + gid + ')"/>' +
    '<path d="' + d + '" fill="none" stroke="' + color + '" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>' +
    dots + labels + chip +
    "</svg>";
}

// ---------------------------------------------------------------------------
// Grouped vertical bars — svgBars({ groups:[{label, values:[v..]}], series:[{name,color}], fmt })
// ---------------------------------------------------------------------------
export function svgBars(opts) {
  const groups = opts.groups || [];
  const series = opts.series || [{ name: "A", color: C.teal }, { name: "B", color: C.blue }];
  const fmt = opts.fmt || fmtCompact;
  const W = 560, H = opts.height || 220;
  const padL = 46, padR = 14, padT = 26, padB = 26;
  if (!groups.length) return emptyChart(W, H, "No data yet");
  const iw = W - padL - padR, ih = H - padT - padB;

  let vmax = 0;
  groups.forEach(function (g) { (g.values || []).forEach(function (v) { vmax = Math.max(vmax, num(v)); }); });
  if (vmax <= 0) vmax = 1;
  vmax *= 1.12;

  let grid = "";
  for (let g = 0; g <= 3; g += 1) {
    const gv = (vmax * g) / 3;
    const gy = padT + ih - (gv / vmax) * ih;
    grid += '<line x1="' + padL + '" y1="' + gy + '" x2="' + (W - padR) + '" y2="' + gy + '" stroke="' + C.grid + '" stroke-width="0.6"/>' +
      '<text x="' + (padL - 6) + '" y="' + (gy + 3) + '" class="ch-tick" text-anchor="end">' + esc(fmt(gv)) + "</text>";
  }

  const groupW = iw / groups.length;
  const nSeries = series.length;
  const barW = Math.min(26, (groupW * 0.62) / nSeries);

  let bars = "", labels = "";
  groups.forEach(function (g, gi) {
    const cx = padL + groupW * gi + groupW / 2;
    (g.values || []).forEach(function (v, si) {
      const h = Math.max(1, (num(v) / vmax) * ih);
      const x = cx - ((nSeries * barW) / 2) + si * barW;
      const y = padT + ih - h;
      const col = (series[si] && series[si].color) || C.teal;
      bars += '<rect x="' + x.toFixed(1) + '" y="' + y.toFixed(1) + '" width="' + (barW - 4).toFixed(1) + '" height="' + h.toFixed(1) + '" rx="3" fill="' + col + '" fill-opacity="0.85">' +
        "<title>" + esc(g.label + " · " + ((series[si] && series[si].name) || "") + ": " + fmt(num(v))) + "</title></rect>";
    });
    labels += '<text x="' + cx.toFixed(1) + '" y="' + (H - 8) + '" class="ch-tick" text-anchor="middle">' + esc(g.label) + "</text>";
  });

  let legend = "";
  series.forEach(function (s, i) {
    legend += '<g transform="translate(' + (padL + i * 130) + ',10)">' +
      '<rect width="9" height="9" rx="2" fill="' + s.color + '"/>' +
      '<text x="14" y="8" class="ch-legend">' + esc(s.name) + "</text></g>";
  });

  return '<svg viewBox="0 0 ' + W + " " + H + '" class="chart" role="img">' + legend + grid + bars + labels + "</svg>";
}

// ---------------------------------------------------------------------------
// Horizontal bars — svgHBars({ rows:[{label,value}], fmt, color, valueFmt })
// ---------------------------------------------------------------------------
export function svgHBars(opts) {
  const rows = (opts.rows || []).map(function (r) { return { label: String(r.label), value: num(r.value) }; });
  const fmt = opts.fmt || fmtCompact;
  const color = opts.color || C.teal;
  const labelW = opts.labelWidth || 132;
  const rowH = opts.rowHeight || 30;
  const W = 560;
  const H = Math.max(60, rows.length * rowH + 12);
  if (!rows.length) return emptyChart(W, 90, "No data yet");
  const valW = 64;
  const barMax = W - labelW - valW - 8;
  const vmax = Math.max.apply(null, rows.map(function (r) { return r.value; }).concat([1]));

  let out = "";
  rows.forEach(function (r, i) {
    const y = 6 + i * rowH;
    const w = Math.max(2, (r.value / vmax) * barMax);
    const c = opts.colorFor ? opts.colorFor(r) : color;
    out += '<text x="' + (labelW - 8) + '" y="' + (y + rowH / 2 + 4) + '" class="ch-tick ch-tick-label" text-anchor="end">' + esc(truncate(r.label, 18)) + "</text>" +
      '<rect x="' + labelW + '" y="' + (y + 5) + '" width="' + w.toFixed(1) + '" height="' + (rowH - 10) + '" rx="4" fill="' + c + '" fill-opacity="0.8">' +
      "<title>" + esc(r.label + ": " + fmt(r.value)) + "</title></rect>" +
      '<text x="' + (labelW + w + 6).toFixed(1) + '" y="' + (y + rowH / 2 + 4) + '" class="ch-val">' + esc(fmt(r.value)) + "</text>";
  });
  return '<svg viewBox="0 0 ' + W + " " + H + '" class="chart" role="img">' + out + "</svg>";
}

function truncate(s, n) {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

// ---------------------------------------------------------------------------
// Donut — svgDonut({ rows:[{label,value,color}], centerValue, centerLabel, fmt })
// ---------------------------------------------------------------------------
export function svgDonut(opts) {
  const rows = (opts.rows || []).map(function (r, i) {
    return { label: String(r.label), value: num(r.value), color: r.color || [C.teal, C.blue, C.violet, C.amber][i % 4] };
  });
  const fmt = opts.fmt || fmtCompact;
  const W = 560, H = opts.height || 190;
  const total = rows.reduce(function (s, r) { return s + r.value; }, 0);
  if (!rows.length || total <= 0) return emptyChart(W, H, "No data yet");

  const cx = 100, cy = H / 2, r = 58, sw = 24;
  const circ = 2 * Math.PI * r;
  let acc = 0, arcs = "";
  rows.forEach(function (row) {
    const frac = row.value / total;
    const dash = (frac * circ).toFixed(2) + " " + circ.toFixed(2);
    arcs += '<circle cx="' + cx + '" cy="' + cy + '" r="' + r + '" fill="none" stroke="' + row.color + '" stroke-width="' + sw + '" stroke-dasharray="' + dash + '" stroke-dashoffset="' + (-acc * circ).toFixed(2) + '" transform="rotate(-90 ' + cx + " " + cy + ')">' +
      "<title>" + esc(row.label + ": " + fmt(row.value) + " (" + Math.round(frac * 100) + "%)") + "</title></circle>";
    acc += frac;
  });

  const center =
    '<text x="' + cx + '" y="' + (cy - 2) + '" class="ch-center" text-anchor="middle">' + esc(opts.centerValue || fmt(total)) + "</text>" +
    '<text x="' + cx + '" y="' + (cy + 16) + '" class="ch-center-sub" text-anchor="middle">' + esc(opts.centerLabel || "TOTAL") + "</text>";

  let legend = "";
  rows.forEach(function (row, i) {
    const ly = 34 + i * 30;
    const pct = Math.round((row.value / total) * 100);
    legend += '<g>' +
      '<rect x="216" y="' + (ly - 9) + '" width="10" height="10" rx="2.5" fill="' + row.color + '"/>' +
      '<text x="232" y="' + ly + '" class="ch-legend-lg">' + esc(row.label) + "</text>" +
      '<text x="540" y="' + ly + '" class="ch-legend-lg ch-val" text-anchor="end">' + esc(fmt(row.value)) + " · " + pct + "%</text></g>";
  });

  return '<svg viewBox="0 0 ' + W + " " + H + '" class="chart" role="img">' + arcs + center + legend + "</svg>";
}

// ---------------------------------------------------------------------------
// Single stacked horizontal bar — svgStacked({ segments:[{label,value,color}], fmt })
// ---------------------------------------------------------------------------
export function svgStacked(opts) {
  const segs = (opts.segments || []).map(function (s) { return { label: String(s.label), value: num(s.value), color: s.color || C.teal }; });
  const fmt = opts.fmt || fmtCompact;
  const W = 560, barH = 24, H = 46 + Math.ceil(segs.length / 2) * 22;
  const total = segs.reduce(function (s, x) { return s + x.value; }, 0);
  if (!segs.length || total <= 0) return emptyChart(W, 90, "No data yet");
  const gid = uid("clip");

  let x = 0, rects = "", legend = "";
  segs.forEach(function (s) {
    const w = (s.value / total) * W;
    rects += '<rect x="' + x.toFixed(1) + '" y="0" width="' + Math.max(0, w - 1).toFixed(1) + '" height="' + barH + '" fill="' + s.color + '">' +
      "<title>" + esc(s.label + ": " + fmt(s.value)) + "</title></rect>";
    x += w;
  });
  segs.forEach(function (s, i) {
    const col = i % 2, row = Math.floor(i / 2);
    const lx = col * (W / 2), ly = barH + 22 + row * 22;
    legend += '<g transform="translate(' + lx + "," + ly + ')">' +
      '<rect width="9" height="9" rx="2" fill="' + s.color + '"/>' +
      '<text x="14" y="8" class="ch-legend">' + esc(s.label) + " — " + esc(fmt(s.value)) + "</text></g>";
  });

  return '<svg viewBox="0 0 ' + W + " " + H + '" class="chart" role="img">' +
    '<defs><clipPath id="' + gid + '"><rect x="0" y="0" width="' + W + '" height="' + barH + '" rx="7"/></clipPath></defs>' +
    '<g clip-path="url(#' + gid + ')">' + rects + "</g>" +
    '<rect x="0" y="0" width="' + W + '" height="' + barH + '" rx="7" fill="none" stroke="' + C.grid + '"/>' +
    legend +
    "</svg>";
}

// ---------------------------------------------------------------------------
// Semicircular gauge — svgGauge({ value, max, label, sub, color, thresholds })
// value/max in same units; thresholds: [{upto, color}] fractions 0..1
// ---------------------------------------------------------------------------
export function svgGauge(opts) {
  const max = num(opts.max, 100) || 100;
  const value = Math.max(0, Math.min(max, num(opts.value)));
  const frac = value / max;
  const W = 210, H = 124, cx = 105, cy = 104, r = 80;
  const len = Math.PI * r;

  let color = opts.color;
  if (!color && opts.thresholds) {
    color = C.teal;
    for (let i = 0; i < opts.thresholds.length; i += 1) {
      if (frac <= opts.thresholds[i].upto) { color = opts.thresholds[i].color; break; }
      color = opts.thresholds[i].color;
    }
  }
  if (!color) color = C.teal;

  const arc = "M " + (cx - r) + " " + cy + " A " + r + " " + r + " 0 0 1 " + (cx + r) + " " + cy;
  const display = opts.display !== undefined ? String(opts.display) : String(Math.round(value));

  return '<svg viewBox="0 0 ' + W + " " + H + '" class="chart gauge" role="img">' +
    '<path d="' + arc + '" fill="none" stroke="' + C.grid + '" stroke-width="13" stroke-linecap="round"/>' +
    '<path d="' + arc + '" fill="none" stroke="' + color + '" stroke-width="13" stroke-linecap="round" stroke-dasharray="' + (len * frac).toFixed(1) + " " + len.toFixed(1) + '"/>' +
    '<text x="' + cx + '" y="' + (cy - 22) + '" class="gauge-val" text-anchor="middle" fill="' + color + '">' + esc(display) + "</text>" +
    '<text x="' + cx + '" y="' + (cy - 2) + '" class="gauge-label" text-anchor="middle">' + esc(opts.label || "") + "</text>" +
    (opts.sub ? '<text x="' + cx + '" y="' + (cy + 16) + '" class="gauge-sub" text-anchor="middle">' + esc(opts.sub) + "</text>" : "") +
    "</svg>";
}

// ---------------------------------------------------------------------------
function emptyChart(W, H, msg) {
  return '<svg viewBox="0 0 ' + W + " " + H + '" class="chart" role="img">' +
    '<rect x="0" y="0" width="' + W + '" height="' + H + '" fill="none"/>' +
    '<text x="' + W / 2 + '" y="' + H / 2 + '" class="ch-tick" text-anchor="middle">' + esc(msg) + "</text></svg>";
}
