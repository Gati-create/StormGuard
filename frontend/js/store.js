// Tiny pub/sub + session cache for the last simulation result and static lookups.

const listeners = {};
const SIM_KEY = "rs_last_simulation";

export function on(event, fn) {
  if (!listeners[event]) listeners[event] = [];
  listeners[event].push(fn);
  return function off() {
    const arr = listeners[event] || [];
    const i = arr.indexOf(fn);
    if (i >= 0) arr.splice(i, 1);
  };
}

export function emit(event, data) {
  (listeners[event] || []).slice().forEach(function (fn) {
    try { fn(data); } catch (e) { /* listener errors never break emitters */ }
  });
}

export function saveSimulation(sim) {
  try {
    sessionStorage.setItem(SIM_KEY, JSON.stringify({ at: Date.now(), sim: sim }));
  } catch (e) { /* storage may be unavailable; pub/sub still works */ }
  emit("simulation", sim);
}

export function loadSimulation() {
  try {
    const raw = sessionStorage.getItem(SIM_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && parsed.sim ? parsed.sim : null;
  } catch (e) {
    return null;
  }
}

// One-per-session caches for static reference data (zone list, public config).
let zonesCache = null;
let configCache = null;

export function getZonesCache() { return zonesCache; }
export function setZonesCache(z) { zonesCache = z; }
export function getConfigCache() { return configCache; }
export function setConfigCache(c) { configCache = c; }
