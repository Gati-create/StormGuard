// Judge Mode — landing view; launches the presentation engine (js/judge.js).

import { viewHead, panel, esc } from "../components.js";
import { enterPresentationMode } from "../judge.js";

export function render(el) {
  el.innerHTML =
    viewHead(
      "Judge Mode",
      "A scripted, deterministic 10-stage walkthrough of the entire platform — built for live demos",
      null
    ) +
    '<div class="judge-hero panel">' +
      '<div class="judge-hero-icon">🎬</div>' +
      '<h2 class="judge-hero-title">START JUDGE DEMO</h2>' +
      '<p class="judge-hero-text">' +
        "Resets all demo data to a deterministic baseline, then walks through: " +
        "normal conditions → extreme weather → AI risk detection → exposure → parametric trigger → " +
        "eligibility → fraud check → payout → financial impact → business viability. " +
        "Every number is computed live by the backend during the show." +
      "</p>" +
      '<button class="btn btn-accent btn-xl" id="judge-start">▶ START JUDGE DEMO</button>' +
      '<div class="judge-controls-hint">' +
        "<span><strong>▶ AUTO</strong> advances every 6s</span><span><strong>← →</strong> navigate</span>" +
        "<span><strong>Space</strong> play/pause</span><span><strong>Esc</strong> exit</span>" +
      "</div>" +
    "</div>" +
    panel("The 10 stages",
      '<div class="judge-stages">' +
        ["1 · NORMAL CONDITIONS", "2 · EXTREME WEATHER", "3 · AI RISK DETECTION", "4 · RIDER EXPOSURE",
         "5 · PARAMETRIC TRIGGER", "6 · ELIGIBILITY", "7 · FRAUD CHECK", "8 · PAYOUT",
         "9 · PLATFORM FINANCIAL IMPACT", "10 · BUSINESS VIABILITY"].map(function (s) {
          return '<span class="judge-stage-chip">' + esc(s) + "</span>";
        }).join("") +
      "</div>" +
      '<p class="muted-text" style="margin-top:12px">Each stage answers five questions: what happened, why, what the AI did, ' +
      "what the business did, and what the rider received.</p>");

  el.querySelector("#judge-start").addEventListener("click", function () {
    enterPresentationMode();
  });
}
