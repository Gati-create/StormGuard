// Formatting helpers — HKD (K/M compaction), Western digit grouping, percents, time.

function trimDec(v, d) {
  const s = Number(v).toFixed(d);
  return s.replace(/\.0+$/, "").replace(/(\.\d*?)0+$/, "$1");
}

// HK$496 · HK$4,200 · HK$52,300 · HK$885K · HK$1.7M
export function fmtINR(n) {
  if (n === null || n === undefined || n === "" || isNaN(Number(n))) return "—";
  const num = Number(n);
  const sign = num < 0 ? "−" : "";
  const a = Math.abs(num);
  if (a >= 1e6) return sign + "HK$" + trimDec(a / 1e6, a >= 1e7 ? 1 : 2) + "M";
  if (a >= 1e4) return sign + "HK$" + trimDec(a / 1e3, 1) + "K";
  return sign + "HK$" + Math.round(a).toLocaleString("en-HK");
}

// Full HKD without K/M compaction (HK$1,694,447) — for exact figures.
export function fmtINRFull(n) {
  if (n === null || n === undefined || n === "" || isNaN(Number(n))) return "—";
  const num = Number(n);
  const sign = num < 0 ? "−" : "";
  return sign + "HK$" + Math.round(Math.abs(num)).toLocaleString("en-HK");
}

// 12,482 — Western digit grouping.
export function fmtNum(n) {
  if (n === null || n === undefined || n === "" || isNaN(Number(n))) return "—";
  return Math.round(Number(n)).toLocaleString("en-HK");
}

// 0.577 → "57.7%" (dec configurable; fmtPct(0.82, 0) → "82%")
export function fmtPct(x, dec) {
  if (x === null || x === undefined || x === "" || isNaN(Number(x))) return "—";
  const d = dec === undefined ? 1 : dec;
  return (Number(x) * 100).toFixed(d) + "%";
}

// 0.83 → "83%" convenience for confidence-style fractions.
export function fmtPctInt(x) { return fmtPct(x, 0); }

export function fmtHours(h) {
  if (h === null || h === undefined || isNaN(Number(h))) return "—";
  return trimDec(Number(h), 1) + "h";
}

export function timeAgo(iso) {
  if (!iso) return "—";
  const s0 = String(iso);
  const t = Date.parse(/Z|[+-]\d{2}:?\d{2}$/.test(s0) ? s0 : s0 + "Z");
  if (isNaN(t)) return s0;
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return Math.floor(s / 60) + "m ago";
  if (s < 86400) return Math.floor(s / 3600) + "h ago";
  const d = Math.floor(s / 86400);
  return d + (d === 1 ? "d ago" : "d ago");
}

export function fmtTime(iso) {
  if (!iso) return "—";
  const s0 = String(iso);
  const t = Date.parse(/Z|[+-]\d{2}:?\d{2}$/.test(s0) ? s0 : s0 + "Z");
  if (isNaN(t)) return s0;
  const d = new Date(t);
  const date = d.toLocaleDateString("en-HK", { day: "2-digit", month: "short" });
  const time = d.toLocaleTimeString("en-HK", { hour: "2-digit", minute: "2-digit", hour12: false });
  return date + ", " + time;
}

// Compact number for chart axis labels: 12482 → "12.5k", 1840000 → "18.4L"
export function fmtCompact(n) {
  if (n === null || n === undefined || isNaN(Number(n))) return "—";
  const a = Math.abs(Number(n));
  if (a >= 1e7) return trimDec(a / 1e7, 1) + "Cr";
  if (a >= 1e5) return trimDec(a / 1e5, 1) + "L";
  if (a >= 1e3) return trimDec(a / 1e3, 1) + "k";
  return String(Math.round(Number(n) * 100) / 100);
}
