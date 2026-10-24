// ============================================================================
// AI Refill Prediction Engine — pure calculation core
// ----------------------------------------------------------------------------
// This module is the SINGLE SOURCE OF TRUTH for every refill calculation. The
// UI (Refill.jsx) only formats and displays the output of `computePrediction`.
// Nothing below is hardcoded: every output is derived from the input form
// using the business rules:
//
//   Daily Consumption            = Daily Dosage Frequency × Quantity Per Dose
//   Remaining Stock              = Manual Stock Update  (if provided)
//                                  else Initial Quantity − (Elapsed Days × Daily Consumption)
//   Remaining Days               = Remaining Stock ÷ Effective Daily Consumption
//   Estimated Depletion Date     = Today + Remaining Days
//   Recommended Refill Date      = Estimated Depletion Date − Buffer Days
//   Expected Doses               = Elapsed Days × Daily Frequency
//   Taken Doses                  = Expected Doses − Missed Doses
//   Effective Daily Consumption  = Taken Doses ÷ Elapsed Days (else prescribed rate)
//   Adherence                    = Taken Doses ÷ Expected Doses × 100
//
// Validation rules (impossible inputs are rejected, never silently clamped):
//   · Missed Doses > Expected Doses          → reject
//   · Tracking Start Date > Today            → reject
//   · Remaining Stock < 0                    → reject
//   · Initial Quantity ≤ 0                   → reject
//   · Dosage Frequency ≤ 0                   → reject
//   · Quantity Per Dose ≤ 0                  → reject
//   · Negative manual stock / missed doses   → reject
// ============================================================================

export const VALID_BUFFER_DAYS = [3, 5, 7];
export const DAY_MS = 24 * 60 * 60 * 1000;

// ── Date / number helpers ──────────────────────────────────────────────────

export const parseNum = (value) => {
  if (value === null || value === undefined || value === "") return 0;
  const n = parseFloat(value);
  return Number.isFinite(n) && n >= 0 ? n : 0;
};

export const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());

export const parseISODate = (raw) => {
  const parts = raw.split("-").map(Number);
  if (parts.length !== 3 || parts.some((p) => !Number.isInteger(p) || p < 0)) return null;
  return new Date(parts[0], parts[1] - 1, parts[2]);
};

export const addDays = (date, days) => {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
};

export const daysBetween = (from, to) =>
  Math.round((startOfDay(to) - startOfDay(from)) / DAY_MS);

export const formatDateLabel = (d) =>
  d.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

// ── Validation ──────────────────────────────────────────────────────────────

// Returns "" when the inputs are *possible*, otherwise a rejection message for
// an impossible input. Incompleteness (empty required fields) is intentionally
// NOT treated as a rejection here — the UI handles that separately, so live
// typing does not produce "please fill in" noise.
export function validateForm(form = {}) {
  const initialQtyStr = (form.initialQty ?? "").trim();
  const freqStr = (form.dosageFrequency ?? "").trim();
  const doseStr = (form.qtyPerDose ?? "").trim();
  const missedRaw = (form.missedDoses ?? "").trim();
  const manualStockStr = (form.manualStock ?? "").trim();
  const trackingRaw = (form.trackingStartDate ?? "").trim();
  const today = startOfDay(new Date());

  // When provided, buffer days must be one of the supported values (3, 5 or 7).
  // If omitted, computePrediction falls back to the documented default of 5.
  if ((form.bufferDays ?? "").trim() !== "" && !VALID_BUFFER_DAYS.includes(parseInt(form.bufferDays, 10))) {
    return "Refill Buffer Days must be 3, 5 or 7 days.";
  }
  // Quantity / frequency / dose must be strictly positive when provided.
  if (initialQtyStr !== "" && parseFloat(initialQtyStr) <= 0) {
    return "Initial Medicine Quantity must be greater than zero.";
  }
  if (freqStr !== "" && parseFloat(freqStr) <= 0) {
    return "Daily Dosage Frequency must be greater than zero.";
  }
  if (doseStr !== "" && parseFloat(doseStr) <= 0) {
    return "Quantity Consumed Per Dose must be greater than zero.";
  }
  // No negative counts.
  if (missedRaw !== "" && parseFloat(missedRaw) < 0) {
    return "Missed doses cannot be negative.";
  }
  if (manualStockStr !== "" && parseFloat(manualStockStr) < 0) {
    return "Manual stock cannot be negative.";
  }
  // Tracking start date must not be in the future.
  if (trackingRaw !== "") {
    const start = parseISODate(trackingRaw);
    if (!start || Number.isNaN(start.getTime()) || start.getTime() > today.getTime()) {
      return "Tracking Start Date cannot be in the future.";
    }
    const elapsedDays = Math.max(0, daysBetween(start, today));
    // Missed doses can never exceed the doses that were actually expected.
    // Only meaningful once the frequency (and thus expected doses) is known.
    const expectedDoses = elapsedDays * parseNum(freqStr);
    if (freqStr !== "" && missedRaw !== "" && parseNum(missedRaw) > expectedDoses) {
      return `Missed doses (${parseNum(missedRaw)}) cannot exceed expected doses (${expectedDoses}).`;
    }
    // Remaining stock can never be negative (unless overridden manually).
    // Only meaningful once the initial quantity is known.
    if (initialQtyStr !== "" && manualStockStr === "") {
      const consumed = elapsedDays * parseNum(freqStr) * parseNum(doseStr);
      if (consumed > parseNum(initialQtyStr)) {
        return "Initial quantity is too small for the tracking period — remaining stock would be negative.";
      }
    }
  }
  return "";
}

// ── Prediction ──────────────────────────────────────────────────────────────

export function computePrediction(form = {}) {
  const medicineName = (form.medicineName ?? "").trim();
  const initialQty = parseNum(form.initialQty);
  const dosageFrequency = parseNum(form.dosageFrequency);
  const qtyPerDose = parseNum(form.qtyPerDose);
  const missedDoses = parseNum(form.missedDoses);
  const missedDosesProvided = (form.missedDoses ?? "").trim() !== "";
  const manualStockStr = (form.manualStock ?? "").trim();
  const hasManualStock = manualStockStr !== "";
  const manualStock = hasManualStock ? parseNum(manualStockStr) : 0;
  const bufferDays = VALID_BUFFER_DAYS.includes(parseInt(form.bufferDays, 10))
    ? parseInt(form.bufferDays, 10)
    : 5;
  const trackingRaw = (form.trackingStartDate ?? "").trim();
  const hasTrackingDate = trackingRaw !== "";
  const trackingStart = hasTrackingDate ? parseISODate(trackingRaw) : null;
  const trackingStartValid =
    trackingStart !== null && !Number.isNaN(trackingStart.getTime());
  const today = startOfDay(new Date());
  const trackingFuture =
    trackingStartValid && trackingStart.getTime() > today.getTime();
  const elapsedDays =
    trackingStartValid && !trackingFuture
      ? Math.max(0, daysBetween(trackingStart, today))
      : 0;

  // Daily Consumption = Daily Dosage Frequency × Quantity Consumed Per Dose
  const nominalDaily = dosageFrequency * qtyPerDose;

  const baseValid =
    medicineName &&
    initialQty > 0 &&
    dosageFrequency > 0 &&
    qtyPerDose > 0 &&
    !trackingFuture;

  const validationError = validateForm(form);

  if (!baseValid || validationError) {
    return {
      valid: false,
      hasPrediction: false,
      medicineName: medicineName || "your medicine",
      validationError,
    };
  }

  // ── Missed dosage → effective daily consumption ──
  const expectedDoses = elapsedDays * dosageFrequency;
  const takenDoses = Math.max(0, expectedDoses - missedDoses);
  // Effective consumption = taken doses ÷ elapsed days. When tracking hasn't
  // started (elapsed = 0) or every dose was missed (taken = 0) we fall back to
  // the prescribed rate so the prediction stays meaningful.
  const consumptionFallback = elapsedDays > 0 && takenDoses === 0;
  const effectiveDaily =
    elapsedDays > 0 && takenDoses > 0 ? takenDoses / elapsedDays : nominalDaily;

  // ── Remaining stock ──
  let remainingStock;
  if (hasManualStock) {
    // Manual stock update takes priority and anchors today's real stock.
    remainingStock = manualStock;
  } else if (elapsedDays > 0) {
    remainingStock = initialQty - elapsedDays * nominalDaily;
  } else {
    remainingStock = initialQty;
  }
  // Cannot go below zero — validateForm already rejects negative cases.
  remainingStock = Math.max(0, remainingStock);

  // ── Remaining days / depletion / refill ──
  const remainingDays = effectiveDaily > 0 ? remainingStock / effectiveDaily : 0;
  const depletionDays = Math.floor(remainingDays);
  const refillDays = Math.max(0, depletionDays - bufferDays);
  const depletionDate = addDays(today, depletionDays);
  const refillDate = addDays(today, refillDays);

  // ── Adherence % = Taken Doses ÷ Expected Doses × 100 ──
  let adherence = null;
  let adherenceLevel = null;
  if (hasTrackingDate) {
    if (expectedDoses > 0) {
      adherence = Math.round(
        Math.min(100, Math.max(0, (takenDoses / expectedDoses) * 100))
      );
    } else {
      // Tracking started today — no doses expected yet, so nothing was missed.
      adherence = 100;
    }
    adherenceLevel =
      adherence >= 95
        ? "Excellent"
        : adherence >= 80
        ? "Good"
        : adherence >= 60
        ? "Average"
        : "Poor";
  }

  // ── Prediction confidence (never hardcoded; scored from real factors) ──
  // Input completeness, extra inputs, manual-stock availability, tracking
  // duration and prediction consistency all contribute.
  const requiredFilled = [
    medicineName,
    initialQty > 0,
    dosageFrequency > 0,
    qtyPerDose > 0,
  ].filter(Boolean).length;
  const optionalFilled = [
    missedDosesProvided,
    hasManualStock,
    hasTrackingDate,
  ].filter(Boolean).length;
  let confidence = 55;
  confidence += (requiredFilled / 4) * 20; // input completeness
  confidence += (optionalFilled / 3) * 15; // extra inputs provided
  if (hasManualStock) confidence += 8; // manual stock availability
  if (elapsedDays >= 14) confidence += 8; // tracking duration
  else if (elapsedDays >= 7) confidence += 5;
  else if (elapsedDays >= 1) confidence += 3;
  if (adherence !== null && adherence >= 80) confidence += 4; // consistency
  confidence = Math.round(Math.min(98, Math.max(50, confidence)));

  // ── Stock health tiers (based on remaining days) ──
  const stockHealth =
    remainingDays <= 3 ? "Critical" : remainingDays <= 7 ? "Warning" : "Healthy";
  const alertLevel =
    remainingDays <= 1
      ? "Urgent"
      : remainingDays <= 3
      ? "Critical"
      : remainingDays <= 7
      ? "Warning"
      : "Healthy";

  // ── Dynamic notifications (driven entirely by the calculated values) ──
  let reminderMessage;
  if (remainingStock <= 0) {
    reminderMessage = `Your ${medicineName} stock is empty. Please refill immediately.`;
  } else if (depletionDays === 0) {
    reminderMessage = `Your ${medicineName} stock will finish today. Please arrange a refill.`;
  } else if (depletionDays === 1) {
    reminderMessage = `Critical. Your ${medicineName} stock will finish tomorrow.`;
  } else if (depletionDays <= 7) {
    reminderMessage = `Your ${medicineName} medicine is expected to finish in ${depletionDays} days. Please arrange a refill.`;
  } else {
    reminderMessage = `Your ${medicineName} medicine is expected to finish in ${depletionDays} days.`;
  }

  let caregiverMessage;
  if (depletionDays <= 7) {
    caregiverMessage = `Patient's ${medicineName} stock is critically low. Recommended refill date: ${formatDateLabel(refillDate)}.`;
  } else {
    caregiverMessage = `Patient's ${medicineName} stock is expected to last until ${formatDateLabel(depletionDate)}. Recommended refill date: ${formatDateLabel(refillDate)}.`;
  }

  // ── Stock projection: starts at remaining stock, decreases by the effective
  //    daily consumption until it reaches exactly zero (no fake values) ──
  // The graph must end exactly on the calculated depletion day (depletionDays),
  // never one day later. Using Math.ceil here made the projection run a day past
  // the computed depletion timeline for fractional remaining days (e.g. 22.2d
  // produced a day-23 endpoint while the depletion date is today + 22 days).
  const totalDays = Math.max(1, depletionDays);
  const maxPoints = 60;
  const step = Math.max(1, Math.ceil(totalDays / maxPoints));
  const projected = [];
  for (let day = 0; day <= totalDays; day += step) {
    let stock = Math.max(0, Math.round(remainingStock - effectiveDaily * day));
    // The endpoint lands exactly on the calculated depletion day (stock 0) so
    // the graph never shows a residual positive value or a duplicated point.
    if (day === totalDays) stock = 0;
    projected.push({ day, dayLabel: day === 0 ? "Today" : `+${day}d`, stock });
  }
  const lastPoint = projected[projected.length - 1];
  if (lastPoint.day !== totalDays || lastPoint.stock !== 0) {
    projected.push({ day: totalDays, dayLabel: `+${totalDays}d`, stock: 0 });
  }

  return {
    valid: true,
    hasPrediction: true,
    validationError,
    medicineName,
    initialQty,
    dosageFrequency,
    qtyPerDose,
    missedDoses,
    missedDosesProvided,
    hasManualStock,
    manualStock,
    hasTrackingDate,
    trackingStartDate: trackingRaw,
    trackingFuture,
    elapsedDays,
    daysPassed: elapsedDays, // backward-compatible alias
    bufferDays,
    nominalDaily,
    avgDaily: nominalDaily, // backward-compatible alias
    effectiveDaily,
    consumptionFallback,
    expectedDoses,
    takenDoses,
    remainingStock,
    remainingDays,
    depletionDays,
    refillDays,
    depletionDateLabel: formatDateLabel(depletionDate),
    refillDateLabel: formatDateLabel(refillDate),
    adherence,
    adherenceLevel,
    confidence,
    stockHealth,
    alertLevel,
    reminderMessage,
    caregiverMessage,
    projected,
  };
}
