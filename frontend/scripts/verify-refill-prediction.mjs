// ============================================================================
// AI Refill Prediction Engine — complete regression verification
// ----------------------------------------------------------------------------
// Run with:  node scripts/verify-refill-prediction.mjs
//
// Verifies every business rule against the real engine
// (src/utils/refillPrediction.js) — the same code the UI uses.
// ============================================================================

import { computePrediction, validateForm } from "../src/utils/refillPrediction.js";

const DAY_MS = 24 * 60 * 60 * 1000;
const fmt = (n) => (Number.isInteger(n) ? `${n}` : n.toFixed(2));
const near = (a, b, eps = 0.01) => Math.abs(a - b) <= eps;

const isoDaysFromToday = (days) => {
  const d = new Date(Date.now() + days * DAY_MS);
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
};
const isoToday = isoDaysFromToday(0);
const isoTomorrow = isoDaysFromToday(1); // future → invalid

let passed = 0;
let failed = 0;

const check = (label, cond, detail) => {
  if (cond) {
    passed++;
    console.log(`  ✔ ${label}${detail ? `  (${detail})` : ""}`);
  } else {
    failed++;
    console.error(`  ✘ ${label}${detail ? `  (${detail})` : ""}`);
  }
};

console.log("AI Refill Prediction Engine — Regression Verification\n");

// ── Scenario 1: 60 tablets, 2/day, 1/dose, 0 missed → 30 days ───────────────
console.log("Scenario 1 — 60 tabs, 2/day, 1/dose, 0 missed → expect 30 days");
{
  const p = computePrediction({
    medicineName: "Amlodipine",
    initialQty: "60",
    dosageFrequency: "2",
    qtyPerDose: "1",
    missedDoses: "0",
    bufferDays: "5",
  });
  check("valid", p.valid && p.hasPrediction);
  check("daily consumption = 2 × 1 = 2", near(p.nominalDaily, 2), `got ${fmt(p.nominalDaily)}`);
  check("remaining stock = 60", near(p.remainingStock, 60), `got ${fmt(p.remainingStock)}`);
  check("remaining days = 60 ÷ 2 = 30", near(p.remainingDays, 30), `got ${fmt(p.remainingDays)}`);
  check("depletion days = 30", p.depletionDays === 30, `got ${p.depletionDays}`);
  check("refill days (buffer 5) = 30 − 5 = 25", p.refillDays === 25, `got ${p.refillDays}`);
}

// ── Scenario 2: 100 tablets, 2/day, manual stock 4 → 2 days ─────────────────
console.log("\nScenario 2 — 100 tabs, 2/day, manual stock 4 → expect 2 days");
{
  const p = computePrediction({
    medicineName: "X",
    initialQty: "100",
    dosageFrequency: "2",
    qtyPerDose: "1",
    manualStock: "4",
    bufferDays: "5",
  });
  check("remaining stock = manual stock = 4", near(p.remainingStock, 4), `got ${fmt(p.remainingStock)}`);
  check("remaining days = 4 ÷ 2 = 2", near(p.remainingDays, 2), `got ${fmt(p.remainingDays)}`);
  check("depletion days = 2", p.depletionDays === 2, `got ${p.depletionDays}`);
  check("alert = Critical (≤ 3 days)", p.alertLevel === "Critical", `got ${p.alertLevel}`);
}

// ── Scenario 3: 100 tablets, 3/day, no manual stock → 33 days ───────────────
console.log("\nScenario 3 — 100 tabs, 3/day, no manual stock → expect 33 days");
{
  const p = computePrediction({
    medicineName: "X",
    initialQty: "100",
    dosageFrequency: "3",
    qtyPerDose: "1",
    bufferDays: "5",
  });
  check("remaining days = 100 ÷ 3 = 33.33", near(p.remainingDays, 100 / 3), `got ${fmt(p.remainingDays)}`);
  check("depletion days = 33", p.depletionDays === 33, `got ${p.depletionDays}`);
}

// ── Scenario 4: tracking 10 days ago, missed 5 → adherence & prediction change
console.log("\nScenario 4 — tracking 10 days ago, missed 5 of 20");
{
  const withMissed = computePrediction({
    medicineName: "X",
    initialQty: "100",
    dosageFrequency: "2",
    qtyPerDose: "1",
    missedDoses: "5",
    trackingStartDate: isoDaysFromToday(-10),
    bufferDays: "5",
  });
  const withoutMissed = computePrediction({
    medicineName: "X",
    initialQty: "100",
    dosageFrequency: "2",
    qtyPerDose: "1",
    missedDoses: "0",
    trackingStartDate: isoDaysFromToday(-10),
    bufferDays: "5",
  });
  check("elapsed days = 10", withMissed.elapsedDays === 10, `got ${withMissed.elapsedDays}`);
  check("expected doses = 10 × 2 = 20", withMissed.expectedDoses === 20, `got ${withMissed.expectedDoses}`);
  check("taken doses = 20 − 5 = 15", withMissed.takenDoses === 15, `got ${withMissed.takenDoses}`);
  check("effective daily = 15 ÷ 10 = 1.5", near(withMissed.effectiveDaily, 1.5), `got ${fmt(withMissed.effectiveDaily)}`);
  check("remaining stock = 100 − (10 × 2) = 80", near(withMissed.remainingStock, 80), `got ${fmt(withMissed.remainingStock)}`);
  check("remaining days = 80 ÷ 1.5 = 53.33", near(withMissed.remainingDays, 80 / 1.5), `got ${fmt(withMissed.remainingDays)}`);
  check("adherence = 15 ÷ 20 × 100 = 75%", withMissed.adherence === 75, `got ${withMissed.adherence}%`);
  check("adherence level = Average (75%)", withMissed.adherenceLevel === "Average", `got ${withMissed.adherenceLevel}`);
  check(
    "adherence changed vs 0 missed (75 vs 100)",
    withMissed.adherence !== withoutMissed.adherence,
    `missed=${withMissed.adherence}%, none=${withoutMissed.adherence}%`
  );
  check(
    "prediction changed vs 0 missed",
    !near(withMissed.remainingDays, withoutMissed.remainingDays),
    `missed=${fmt(withMissed.remainingDays)}d, none=${fmt(withoutMissed.remainingDays)}d`
  );
}

// ── Scenario 5: buffer days 3 / 5 / 7 → refill date changes ─────────────────
console.log("\nScenario 5 — buffer days 3 / 5 / 7 → refill date changes");
{
  const base = { medicineName: "X", initialQty: "60", dosageFrequency: "2", qtyPerDose: "1", missedDoses: "0" };
  const r3 = computePrediction({ ...base, bufferDays: "3" });
  const r5 = computePrediction({ ...base, bufferDays: "5" });
  const r7 = computePrediction({ ...base, bufferDays: "7" });
  check("buffer 3 → refill = 30 − 3 = 27 days", r3.refillDays === 27, `got ${r3.refillDays}`);
  check("buffer 5 → refill = 30 − 5 = 25 days", r5.refillDays === 25, `got ${r5.refillDays}`);
  check("buffer 7 → refill = 30 − 7 = 23 days", r7.refillDays === 23, `got ${r7.refillDays}`);
  check(
    "all three refill dates differ",
    new Set([r3.refillDateLabel, r5.refillDateLabel, r7.refillDateLabel]).size === 3,
    `${r3.refillDateLabel} | ${r5.refillDateLabel} | ${r7.refillDateLabel}`
  );
  check(
    "depletion date unchanged by buffer",
    r3.depletionDateLabel === r5.depletionDateLabel && r5.depletionDateLabel === r7.depletionDateLabel
  );
}

// ── Scenario 6: missed doses > expected doses → must reject ─────────────────
console.log("\nScenario 6 — missed doses > expected doses → must reject");
{
  const form = {
    medicineName: "X",
    initialQty: "100",
    dosageFrequency: "2",
    qtyPerDose: "1",
    missedDoses: "25",
    trackingStartDate: isoDaysFromToday(-10),
    bufferDays: "5",
  };
  const err = validateForm(form);
  check("validateForm rejects", err !== "", `got: ${err || "NO ERROR"}`);
  const p = computePrediction(form);
  check("prediction suppressed (no results shown)", !p.valid && !p.hasPrediction);
}

// ── Validation rules: reject every impossible input ─────────────────────────
console.log("\nValidation — reject impossible inputs");
{
  const base = { medicineName: "X", initialQty: "100", dosageFrequency: "2", qtyPerDose: "1" };
  check(
    "missed doses > expected doses → reject",
    validateForm({ ...base, missedDoses: "3", trackingStartDate: isoToday }) !== ""
  );
  check(
    "tracking date > today → reject",
    validateForm({ ...base, trackingStartDate: isoTomorrow }) !== ""
  );
  check(
    "remaining stock < 0 → reject",
    validateForm({ ...base, initialQty: "10", trackingStartDate: isoDaysFromToday(-10) }) !== ""
  );
  check("quantity = 0 → reject", validateForm({ ...base, initialQty: "0" }) !== "");
  check("frequency = 0 → reject", validateForm({ ...base, dosageFrequency: "0" }) !== "");
  check("dose = 0 → reject", validateForm({ ...base, qtyPerDose: "0" }) !== "");
  check("negative manual stock → reject", validateForm({ ...base, manualStock: "-5" }) !== "");
  check("negative missed doses → reject", validateForm({ ...base, missedDoses: "-3" }) !== "");
  check("invalid buffer days → reject", validateForm({ ...base, bufferDays: "9" }) !== "");
}

// ── Adherence: never N/A when a tracking date exists ────────────────────────
console.log("\nAdherence — no N/A bug");
{
  const pToday = computePrediction({
    medicineName: "X",
    initialQty: "100",
    dosageFrequency: "2",
    qtyPerDose: "1",
    missedDoses: "0",
    trackingStartDate: isoToday,
  });
  check("tracking date today → adherence = 100%", pToday.adherence === 100, `got ${pToday.adherence}%`);
  check("tracking date today → level Excellent", pToday.adherenceLevel === "Excellent", `got ${pToday.adherenceLevel}`);
  const p10 = computePrediction({
    medicineName: "X",
    initialQty: "100",
    dosageFrequency: "2",
    qtyPerDose: "1",
    missedDoses: "0",
    trackingStartDate: isoDaysFromToday(-10),
  });
  check("10-day tracking → adherence = 100%", p10.adherence === 100, `got ${p10.adherence}%`);
  const pNone = computePrediction({ medicineName: "X", initialQty: "100", dosageFrequency: "2", qtyPerDose: "1" });
  check("no tracking date → adherence null (N/A allowed)", pNone.adherence === null);
}

// ── Tracking start date affects elapsed days, stock & prediction ────────────
console.log("\nTracking start date — affects elapsed days, stock & prediction");
{
  const tracked = computePrediction({
    medicineName: "X",
    initialQty: "60",
    dosageFrequency: "2",
    qtyPerDose: "1",
    missedDoses: "0",
    trackingStartDate: isoDaysFromToday(-10),
  });
  const untracked = computePrediction({ medicineName: "X", initialQty: "60", dosageFrequency: "2", qtyPerDose: "1", missedDoses: "0" });
  check("elapsed days = 10 when tracked", tracked.elapsedDays === 10, `got ${tracked.elapsedDays}`);
  check(
    "remaining stock drops with tracking (60 → 40)",
    near(tracked.remainingStock, 40),
    `tracked=${fmt(tracked.remainingStock)}, untracked=${fmt(untracked.remainingStock)}`
  );
  check("prediction differs with tracking", !near(tracked.remainingDays, untracked.remainingDays));
  check("expected doses = 20 when tracked", tracked.expectedDoses === 20, `got ${tracked.expectedDoses}`);
}

// ── Stock projection ─────────────────────────────────────────────────────────
console.log("\nStock projection");
{
  const p = computePrediction({ medicineName: "X", initialQty: "100", dosageFrequency: "3", qtyPerDose: "1" });
  check("starts at remaining stock", p.projected[0].stock === p.remainingStock, `got ${p.projected[0].stock}`);
  check("ends exactly at zero", p.projected[p.projected.length - 1].stock === 0, `got ${p.projected[p.projected.length - 1].stock}`);
  const tracked = computePrediction({
    medicineName: "X",
    initialQty: "100",
    dosageFrequency: "2",
    qtyPerDose: "1",
    missedDoses: "5",
    trackingStartDate: isoDaysFromToday(-10),
  });
  const expectedAtDay1 = Math.max(0, Math.round(tracked.remainingStock - tracked.effectiveDaily * 1));
  check(
    "decreases by effective daily consumption",
    tracked.projected[1].stock === expectedAtDay1,
    `got ${tracked.projected[1].stock}, formula ${expectedAtDay1}`
  );
}

// ── Notifications & low-stock tiers ─────────────────────────────────────────
console.log("\nNotifications & low-stock tiers");
{
  const p30 = computePrediction({ medicineName: "X", initialQty: "60", dosageFrequency: "2", qtyPerDose: "1", missedDoses: "0", bufferDays: "5" });
  const p5 = computePrediction({ medicineName: "X", initialQty: "100", dosageFrequency: "2", qtyPerDose: "1", manualStock: "10", bufferDays: "5" });
  const p1 = computePrediction({ medicineName: "X", initialQty: "100", dosageFrequency: "2", qtyPerDose: "1", manualStock: "2", bufferDays: "5" });
  check(
    "30-day / 5-day / 1-day messages all differ",
    new Set([p30.reminderMessage, p5.reminderMessage, p1.reminderMessage]).size === 3
  );
  check("30-day message mentions 30 days", p30.reminderMessage.includes("30 days"), p30.reminderMessage);
  check("1-day message is critical", p1.reminderMessage.includes("tomorrow"), p1.reminderMessage);
  check("caregiver uses calculated refill date", p30.caregiverMessage.includes(p30.refillDateLabel), p30.caregiverMessage);
  check("5-day tier = Warning", p5.alertLevel === "Warning", `got ${p5.alertLevel}`);
  check("1-day tier = Urgent", p1.alertLevel === "Urgent", `got ${p1.alertLevel}`);
  check("30-day tier = Healthy", p30.alertLevel === "Healthy", `got ${p30.alertLevel}`);
}

// ── Prediction confidence is never hardcoded ────────────────────────────────
console.log("\nPrediction confidence");
{
  const base = { medicineName: "X", initialQty: "100", dosageFrequency: "2", qtyPerDose: "1", bufferDays: "5" };
  const minimal = computePrediction(base);
  const rich = computePrediction({
    ...base,
    missedDoses: "0",
    manualStock: "50",
    trackingStartDate: isoDaysFromToday(-15),
  });
  check("confidence is computed (not constant)", minimal.confidence !== rich.confidence, `min=${minimal.confidence}%, rich=${rich.confidence}%`);
  check("confidence within bounds", minimal.confidence >= 50 && minimal.confidence <= 98 && rich.confidence >= 50 && rich.confidence <= 98);
}

// ── Summary ──────────────────────────────────────────────────────────────────
console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
