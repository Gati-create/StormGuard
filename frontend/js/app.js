// App shell: hash router, nav, topbar actions, footer disclaimer, health pill.

import { api } from "./api.js";
import { toastSuccess, toastError } from "./components.js";

import * as overview from "./views/overview.js";
import * as rider from "./views/rider.js";
import * as fleet from "./views/fleet.js";
import * as events from "./views/events.js";
import * as pricing from "./views/pricing.js";
import * as claims from "./views/claims.js";
import * as analytics from "./views/analytics.js";
import * as viability from "./views/viability.js";
import * as simulation from "./views/simulation.js";
import * as audit from "./views/audit.js";
import * as judge from "./views/judge.js";

const ROUTES = {
  "/overview": { mod: overview, title: "Overview" },
  "/rider": { mod: rider, title: "Rider Protection" },
  "/fleet": { mod: fleet, title: "Fleet Risk" },
  "/events": { mod: events, title: "Live Events" },
  "/pricing": { mod: pricing, title: "Pricing" },
  "/claims": { mod: claims, title: "Claims & Fraud" },
  "/analytics": { mod: analytics, title: "Risk Analytics" },
  "/viability": { mod: viability, title: "Business Viability" },
  "/simulation": { mod: simulation, title: "Simulation" },
  "/audit": { mod: audit, title: "Audit Log" },
  "/judge": { mod: judge, title: "Judge Mode" },
};

const FALLBACK_DISCLAIMER =
  "Prototype simulation. Commercial deployment would require appropriate insurance " +
  "licensing/partnerships, actuarial validation, regulatory approval, data protection " +
  "controls and contractual integration with participating platforms.";

let currentPath = null;

function routeFromHash() {
  const h = (location.hash || "").replace(/^#/, "");
  return ROUTES[h] ? h : "/overview";
}

function navigate() {
  const path = routeFromHash();
  if ((location.hash || "") !== "#" + path) {
    history.replaceState(null, "", "#" + path);
  }
  const route = ROUTES[path];

  // Tear down previous view.
  if (currentPath && ROUTES[currentPath] && typeof ROUTES[currentPath].mod.destroy === "function") {
    try { ROUTES[currentPath].mod.destroy(); } catch (e) { /* never block navigation */ }
  }
  const slideover = document.querySelector(".slideover-overlay");
  if (slideover) slideover.remove();
  currentPath = path;

  // Nav active state.
  Array.prototype.forEach.call(document.querySelectorAll(".nav-link"), function (a) {
    a.classList.toggle("active", a.getAttribute("data-route") === path);
  });
  const simBtn = document.querySelector(".nav-sim");
  if (simBtn) simBtn.classList.toggle("active", path === "/simulation");

  document.title = route.title + " · RideShield";
  const view = document.getElementById("view");
  window.scrollTo(0, 0);
  route.mod.render(view);
}

// ---------------------------------------------------------------------------

async function refreshDisclaimer() {
  const footer = document.getElementById("disclaimer");
  if (!footer) return;
  try {
    const cfg = await api.get("/api/config");
    footer.textContent = cfg.disclaimer || FALLBACK_DISCLAIMER;
  } catch (e) {
    footer.textContent = FALLBACK_DISCLAIMER;
  }
}

async function refreshHealth() {
  const pill = document.getElementById("sys-pill");
  if (!pill) return;
  try {
    await api.get("/api/health");
    pill.className = "sys-pill ok";
    pill.innerHTML = '<span class="sys-dot"></span> SYSTEM OPERATIONAL';
  } catch (e) {
    pill.className = "sys-pill down";
    pill.innerHTML = '<span class="sys-dot"></span> BACKEND OFFLINE';
  }
}

async function resetDemo() {
  if (!window.confirm("Reset all demo data to the deterministic baseline?\nThis clears simulated events, claims and payouts.")) return;
  try {
    await api.post("/api/simulation/reset", {});
    toastSuccess("Demo reset — baseline restored.");
  } catch (err) {
    toastError(err.detail || "Reset failed");
    return;
  }
  navigate(); // re-fetch the current view
}

function init() {
  window.addEventListener("hashchange", navigate);
  const resetBtn = document.getElementById("btn-reset");
  if (resetBtn) resetBtn.addEventListener("click", resetDemo);
  const judgeBtn = document.getElementById("btn-judge");
  if (judgeBtn) judgeBtn.addEventListener("click", function () { location.hash = "#/judge"; });

  if (!location.hash) {
    history.replaceState(null, "", "#/overview");
  }
  refreshDisclaimer();
  refreshHealth();
  setInterval(function () {
    if (!document.body.classList.contains("presenting")) refreshHealth();
  }, 30000);
  navigate();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
