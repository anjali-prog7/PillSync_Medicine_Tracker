/**
 * ocrPersistence.js
 * ---------------------------------------------------------------------------
 * Reusable localStorage persistence helpers for the Prescription OCR page.
 * The manual entry form, extracted OCR result, medicine cards and uploaded
 * images are saved automatically after every change and restored on reload.
 * This is purely client-side — no backend, database or API changes.
 *
 * Storage keys are namespaced under "pillSync_ocr_" to match the existing
 * "pillSync_ocr_history" key used by the upload history feature.
 */

const FORM_KEY = "pillSync_ocr_form";
const OCR_KEY = "pillSync_ocr_result";
const MEDICINE_IMG_KEY = "pillSync_ocr_medicine_image";
const PRESCRIPTION_IMG_KEY = "pillSync_ocr_prescription_image";

const ALL_KEYS = [FORM_KEY, OCR_KEY, MEDICINE_IMG_KEY, PRESCRIPTION_IMG_KEY];

/** Default / reset values of the manual medicine entry form. */
export const EMPTY_FORM = {
  medicine_name: "",
  dosage: "",
  quantity: "",
  frequency: "",
  timing: "",
  duration: "",
  disease: "",
  doctor_name: "",
  prescription_notes: "",
  start_date: "",
  end_date: "",
  medicine_type: "TABLET",
};

/* ---------------------------------------------------------------------------
   Low-level safe helpers (never throw, never spam the console)
   --------------------------------------------------------------------------- */

function safeParse(raw) {
  try {
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function safeSet(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false; // quota exceeded / storage unavailable
  }
}

function safeRemove(key) {
  try {
    localStorage.removeItem(key);
  } catch {
    /* ignore */
  }
}

/* ---------------------------------------------------------------------------
   Manual entry form
   --------------------------------------------------------------------------- */

export function saveFormState(formData) {
  safeSet(FORM_KEY, formData || EMPTY_FORM);
}

export function restoreFormState() {
  const stored = safeParse(localStorage.getItem(FORM_KEY));
  if (!stored || typeof stored !== "object") return { ...EMPTY_FORM };
  return { ...EMPTY_FORM, ...stored };
}

/* ---------------------------------------------------------------------------
   OCR result + editable medicine cards
   (also carries status, confidence and engine/`AI Vision` flag)
   --------------------------------------------------------------------------- */

export function saveOCRState(ocrResult, editableMedicines) {
  if (!ocrResult) {
    safeRemove(OCR_KEY);
    return;
  }
  safeSet(OCR_KEY, {
    ocrResult,
    editableMedicines: Array.isArray(editableMedicines) ? editableMedicines : [],
  });
}

export function restoreOCRState() {
  const stored = safeParse(localStorage.getItem(OCR_KEY));
  if (!stored) return { ocrResult: null, editableMedicines: [] };
  return {
    ocrResult: stored.ocrResult || null,
    editableMedicines: Array.isArray(stored.editableMedicines)
      ? stored.editableMedicines
      : [],
  };
}

/* ---------------------------------------------------------------------------
   Uploaded images / files (data URL + file metadata)
   which: "medicine" | "prescription"
   --------------------------------------------------------------------------- */

const imageKey = (which) =>
  which === "prescription" ? PRESCRIPTION_IMG_KEY : MEDICINE_IMG_KEY;

export async function saveImage(which, image) {
  const key = imageKey(which);
  if (!image || (!image.dataUrl && !image.fileName)) {
    safeRemove(key);
    return;
  }
  // Non-image files (e.g. PDF prescriptions) have no data URL — store the
  // metadata only so the file name/section survives a refresh.
  if (!image.dataUrl) {
    safeSet(key, {
      fileName: image.fileName,
      fileType: image.fileType,
      pdf: true,
    });
    return;
  }
  if (safeSet(key, image)) return;
  // Storage quota exceeded — fall back to a smaller copy so the preview still
  // survives a refresh.
  const small = await downscaleDataUrl(image.dataUrl);
  if (small && small !== image.dataUrl) {
    safeSet(key, { ...image, dataUrl: small, downscaled: true });
  }
}

export function restoreImage(which) {
  return safeParse(localStorage.getItem(imageKey(which)));
}

/* ---------------------------------------------------------------------------
   Reset everything
   --------------------------------------------------------------------------- */

export function clearStoredData() {
  ALL_KEYS.forEach(safeRemove);
}

/* ---------------------------------------------------------------------------
   Data URL <-> File helpers
   --------------------------------------------------------------------------- */

/**
 * Rebuild a File object from a stored data URL so the "Extract Info" button
 * keeps working after a refresh without asking the user to re-upload.
 */
export function dataUrlToFile(dataUrl, fileName, fileType) {
  try {
    const parts = dataUrl.split(",");
    const mime =
      (parts[0].match(/:(.*?);/) || [])[1] || fileType || "application/octet-stream";
    const bstr = atob(parts[1]);
    const bytes = new Uint8Array(bstr.length);
    for (let i = 0; i < bstr.length; i += 1) bytes[i] = bstr.charCodeAt(i);
    return new File([bytes], fileName || "uploaded-file", { type: mime });
  } catch {
    return null;
  }
}

/** Downscale an image data URL so it fits inside the localStorage quota. */
function downscaleDataUrl(dataUrl, maxDim = 900, quality = 0.85) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      try {
        const scale = Math.min(1, maxDim / Math.max(img.width, img.height));
        if (scale >= 1) {
          resolve(dataUrl);
          return;
        }
        const canvas = document.createElement("canvas");
        canvas.width = Math.max(1, Math.round(img.width * scale));
        canvas.height = Math.max(1, Math.round(img.height * scale));
        const ctx = canvas.getContext("2d");
        if (!ctx) {
          resolve(dataUrl);
          return;
        }
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        resolve(canvas.toDataURL("image/jpeg", quality));
      } catch {
        resolve(dataUrl);
      }
    };
    img.onerror = () => resolve(dataUrl);
    img.src = dataUrl;
  });
}
