// Simulated Hong Kong district map — hand-rolled SVG from zone map_x/map_y/map_w/map_h
// (viewBox 0 0 400 300). Zones coloured by risk level; click → detail callback.

import { LEVEL_COLORS, C } from "./charts.js";
import { esc } from "./components.js";

export const LEGEND = [
  { level: "LOW", color: LEVEL_COLORS.LOW },
  { level: "MODERATE", color: LEVEL_COLORS.MODERATE },
  { level: "HIGH", color: LEVEL_COLORS.HIGH },
  { level: "SEVERE", color: LEVEL_COLORS.SEVERE },
];

export function levelColor(level) {
  return LEVEL_COLORS[String(level || "").toUpperCase()] || C.muted;
}

// renderCityMap(zones, { selectedId, epicenterId, showScores })
export function renderCityMap(zones, opts) {
  const o = opts || {};
  const list = Array.isArray(zones) ? zones : [];

  let grid = "";
  for (let x = 0; x <= 400; x += 25) {
    grid += '<line x1="' + x + '" y1="0" x2="' + x + '" y2="300" stroke="#16324a" stroke-width="0.4" opacity="0.55"/>';
  }
  for (let y = 0; y <= 300; y += 25) {
    grid += '<line x1="0" y1="' + y + '" x2="400" y2="' + y + '" stroke="#16324a" stroke-width="0.4" opacity="0.55"/>';
  }

  let rects = "";
  list.forEach(function (z) {
    const x = Number(z.map_x) || 0, y = Number(z.map_y) || 0;
    const w = Number(z.map_w) || 40, h = Number(z.map_h) || 30;
    const color = levelColor(z.risk_level);
    const selected = o.selectedId === z.zone_id;
    const epicenter = o.epicenterId === z.zone_id;
    const triggers = Array.isArray(z.active_triggers) ? z.active_triggers : [];
    const score = z.risk_score === null || z.risk_score === undefined ? "" : z.risk_score;

    rects +=
      '<g class="zone-g" data-zone="' + esc(z.zone_id) + '" tabindex="0" role="button" aria-label="' + esc(z.name) + '">' +
        '<rect class="zone-rect" x="' + x + '" y="' + y + '" width="' + w + '" height="' + h + '" rx="8" ' +
          'fill="' + color + '" fill-opacity="' + (selected ? "0.50" : "0.26") + '" ' +
          'stroke="' + color + '" stroke-width="' + (selected ? "2.4" : "1.2") + '"/>' +
        '<text class="zone-name" x="' + (x + w / 2) + '" y="' + (y + h / 2 - (o.showScores === false ? 0 : 2)) + '" text-anchor="middle">' + esc(z.name) + "</text>" +
        (o.showScores === false ? "" :
          '<text class="zone-score" x="' + (x + w / 2) + '" y="' + (y + h / 2 + 11) + '" text-anchor="middle">' +
            (score === "" ? "" : score + (triggers.length ? " ⚡" : "")) + "</text>") +
        (triggers.length ?
          '<circle class="zone-pulse" cx="' + (x + w - 9) + '" cy="' + (y + 9) + '" r="4" fill="' + color + '"/>' +
          '<circle class="zone-pulse-ring" cx="' + (x + w - 9) + '" cy="' + (y + 9) + '" r="4" fill="none" stroke="' + color + '"/>' : "") +
        (epicenter ?
          '<text class="zone-epi" x="' + (x + 6) + '" y="' + (y + 13) + '">◎ EPICENTER</text>' : "") +
        "<title>" + esc(z.name) + " — risk " + esc(score === "" ? "—" : score) +
          (triggers.length ? " · triggers: " + esc(triggers.join(", ")) : "") + "</title>" +
      "</g>";
  });

  const watermark =
    '<text x="396" y="294" text-anchor="end" class="map-watermark">SIMULATED MAP · MOCK DATA</text>' +
    '<text x="4" y="294" class="map-watermark">HONG KONG · FICTIONAL DELIVERY DISTRICTS</text>';

  return '<svg viewBox="0 0 400 300" class="city-map" role="img" aria-label="Simulated city risk map">' +
    grid + rects + watermark + "</svg>";
}

// Attach click / keyboard handlers after the SVG is in the DOM.
export function wireCityMap(container, onZoneClick) {
  if (!container || !onZoneClick) return;
  const nodes = container.querySelectorAll(".zone-g");
  Array.prototype.forEach.call(nodes, function (g) {
    const id = g.getAttribute("data-zone");
    g.addEventListener("click", function () { onZoneClick(id); });
    g.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onZoneClick(id); }
    });
  });
}

export function mapLegendHtml() {
  return '<div class="map-legend">' +
    LEGEND.map(function (l) {
      return '<span class="map-legend-item"><span class="map-dot" style="background:' + l.color + '"></span>' + l.level + "</span>";
    }).join("") +
    '<span class="map-legend-item map-legend-note">Click a zone for detail</span>' +
    "</div>";
}
