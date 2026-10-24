import { useState, useEffect, useCallback, useRef } from "react";
import {
  FaBell,
  FaPlus,
  FaClock,
  FaEdit,
  FaTrash,
  FaSpinner,
  FaCheckCircle,
  FaExclamationCircle,
  FaExclamationTriangle,
} from "react-icons/fa";

import Navbar from "../components/Navbar";
import api from "../services/api";
import usePushNotifications from "../hooks/usePushNotifications";
import "../styles/Reminder.css";

const INITIAL_FORM = {
  medicine: "",
  medicine_id: "",
  disease: "",
  dosage: "",
  times: [],
  frequencyDoses: 1,
  schedule: "",
  repeat: "Daily",
  startDate: "",
  endDate: "",
  push: true,
  email: false,
  sms: false,
  status: "Pending",
};

/* ======================================================
   SCHEDULE OPTIONS (Morning / Afternoon / Evening / Night)
   The schedule is a UI helper only: picking one suggests a
   default time, but the actual reminder ALWAYS fires using
   the final saved date + time.
====================================================== */
const SCHEDULE_OPTIONS = ["Morning", "Afternoon", "Evening", "Night"];
const SCHEDULE_DEFAULT_TIMES = {
  Morning: "08:00",
  Afternoon: "13:00",
  Evening: "18:00",
  Night: "21:00",
};

/* ======================================================
   EXACT-TIME SCHEDULER HELPERS
   All times are parsed/compared in the USER'S LOCAL
   timezone. No UTC is hardcoded anywhere.
====================================================== */
const FIRED_STORAGE_KEY = "pillsync_fired_reminders_v1";

// Max safe setTimeout delay (~24.8 days). Longer horizons are
// re-scheduled in chunks so notifications never fire early/late.
const MAX_TIMEOUT_DELAY = 2147483000;

// Unique key for a reminder schedule. Changes whenever the
// date or time is edited, so an edited reminder can fire again.
const getReminderKey = (item) =>
  `${item.id}|${item.reminder_date}|${item.reminder_time}`;

// Build a local Date from reminder_date (YYYY-MM-DD) and
// reminder_time (HH:MM[:SS]) using the browser's local timezone.
// Returns null for invalid/legacy values so they never get scheduled.
const getTargetDate = (item) => {
  if (!item.reminder_date || !item.reminder_time) return null;
  const [y, m, d] = item.reminder_date.split("-").map(Number);
  const [hh, mm] = item.reminder_time.split(":").map(Number);
  if (
    !y || !m || !d ||
    Number.isNaN(hh) || Number.isNaN(mm) ||
    m < 1 || m > 12 || d < 1 || d > 31 ||
    hh < 0 || hh > 23 || mm < 0 || mm > 59
  ) {
    return null; // invalid date/time — never scheduled
  }
  const target = new Date(y, m - 1, d, hh, mm, 0, 0);
  // Round-trip check: reject impossible dates (e.g. Feb 31) that the
  // Date constructor would silently roll over to a different day.
  if (
    target.getFullYear() !== y ||
    target.getMonth() !== m - 1 ||
    target.getDate() !== d
  ) {
    return null;
  }
  return target;
};

// Persisted map of already-fired reminders { key: firedAtISO }.
// Prevents duplicate notifications across refreshes and keeps
// each reminder triggering exactly once.
const loadFiredMap = () => {
  try {
    return JSON.parse(localStorage.getItem(FIRED_STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
};

const saveFiredMap = (map) => {
  try {
    localStorage.setItem(FIRED_STORAGE_KEY, JSON.stringify(map));
  } catch {
    /* storage unavailable — fire-once still guarded in-session */
  }
};

const isAlreadyFired = (key) =>
  Object.prototype.hasOwnProperty.call(loadFiredMap(), key);

// Local-timezone date string (YYYY-MM-DD) for the default start date.
const getLocalDateString = () => {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
};

/* ======================================================
   TIME NORMALIZATION HELPERS
   The <input type="time"> value can be locale-dependent
   (some browsers return "05:32 PM" in 12-hour locales).
   We ALWAYS send/compare 24-hour "HH:MM" to the backend
   so the stored time exactly matches what the user picked.
====================================================== */
const normalizeTime24h = (value) => {
  if (!value) return "";
  const m = String(value)
    .trim()
    .match(/^(\d{1,2}):(\d{2})(?::\d{2})?\s*(AM|PM)?$/i);
  if (!m) return value;
  let hour = parseInt(m[1], 10);
  const minute = m[2];
  const ampm = m[3] ? m[3].toUpperCase() : "";
  if (ampm === "PM" && hour !== 12) hour += 12;
  if (ampm === "AM" && hour === 12) hour = 0;
  return `${String(hour).padStart(2, "0")}:${minute}`;
};

// Format a 24-hour "HH:MM[:SS]" time as "HH:MM AM/PM" (e.g. "05:32 PM").
const formatTime12h = (value) => {
  if (!value) return "";
  const m = String(value).trim().match(/^(\d{1,2}):(\d{2})/);
  if (!m) return value;
  let hour = parseInt(m[1], 10);
  const minute = m[2];
  const suffix = hour >= 12 ? "PM" : "AM";
  hour = hour % 12 || 12;
  return `${String(hour).padStart(2, "0")}:${minute} ${suffix}`;
};

function Reminders() {
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [medicinesList, setMedicinesList] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [editId, setEditId] = useState(null);
  const [editIds, setEditIds] = useState([]); // All reminder IDs for the group
  const [reminders, setReminders] = useState([]);
  const [message, setMessage] = useState({ type: "", text: "" });
  const [showConfirm, setShowConfirm] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [saving, setSaving] = useState(false);
  const [testingPush, setTestingPush] = useState(false);
  const [emailConfig, setEmailConfig] = useState(null);

  const [formData, setFormData] = useState(INITIAL_FORM);

  /* ── Browser notifications via the backend push queue ── */
  const pushReady = usePushNotifications();

  /* ── Exact-time scheduler state ── */
  const timersRef = useRef({}); // id -> setTimeout id (exact firing)
  const firedSessionRef = useRef(new Set()); // keys fired this session
  const scheduledKeysRef = useRef(new Set()); // keys scheduled this session
  // timeManuallySetRef removed — multiple times now managed via times array

  const showToast = useCallback((type, text) => {
    setMessage({ type, text });
    setTimeout(() => setMessage({ type: "", text: "" }), 6000);
  }, []);

  /* ── Send a REAL test push through the backend (pywebpush) ──
     Never fakes success: the backend reports actual delivery, missing
     subscription, or missing VAPID configuration. */
  const testPush = useCallback(async () => {
    setTestingPush(true);
    try {
      const res = await api.post("reminders/push/test/");
      if (res.data?.status === "sent") {
        showToast(
          "success",
          `Push delivered (${res.data.sent} device${res.data.sent > 1 ? "s" : ""}) — check your browser notification.`
        );
      } else {
        showToast("warning", res.data?.detail || "Push could not be delivered.");
      }
    } catch (err) {
      const detail =
        err?.response?.data?.detail ||
        "Push failed. Enable browser notifications first (lock icon → Site settings → Notifications → Allow), then reload."
      ;
      showToast("warning", detail);
    } finally {
      setTestingPush(false);
    }
  }, [showToast]);

  /* ── Check the server's SMTP setup (no credentials are exposed) ── */
  useEffect(() => {
    let active = true;
    api
      .get("reminders/email-config-check/")
      .then((res) => {
        if (active) setEmailConfig(res.data);
      })
      .catch(() => {
        /* diagnostic only — never block the page */
      });
    return () => {
      active = false;
    };
  }, []);

  const getMedicineName = useCallback(
    (medicineId) => {
      const med = medicinesList.find((m) => m.id === medicineId);
      return med ? med.medicine_name : `Medicine #${medicineId}`;
    },
    [medicinesList]
  );

  const getMedicineDosage = useCallback(
    (medicineId) => {
      const med = medicinesList.find((m) => m.id === medicineId);
      return med ? med.dosage : "—";
    },
    [medicinesList]
  );

  const sendNotification = useCallback(
    (medicine, time) => {
      // Browser notifications are displayed by usePushNotifications(), which
      // consumes the backend's pending-push queue and shows the LIVE medicine
      // name/time returned by the API. The in-app toast stays as immediate
      // feedback on this page (and as the fallback when the Notification API
      // or permission is unavailable).
      showToast("info", `⏰ Time to take ${medicine} at ${time}`);
    },
    [showToast]
  );

  /* ========== Fetch data from API ========== */
  const fetchData = useCallback(async () => {
    const token = localStorage.getItem("access");
    if (!token) {
      showToast("error", "Please login first");
      setPageLoading(false);
      return;
    }
    try {
      const [medRes, remRes] = await Promise.all([
        api.get("medicines/"),
        api.get("reminders/"),
      ]);
      setMedicinesList(medRes.data);
      setReminders(remRes.data);
      console.log("Reminder Loaded:", { count: remRes.data.length, items: remRes.data });
    } catch (error) {
      console.error("Failed to fetch data:", error);
      const status = error.response?.status;
      const detail = error.response?.data?.detail;
      if (status === 401) {
        showToast("error", "Session expired. Please log in again.");
      } else if (status === 500) {
        showToast("error", "Server error. Please try again later.");
      } else {
        showToast(
          "error",
          detail || `Failed to load data (HTTP ${status || "network error"})`
        );
      }
    } finally {
      setPageLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  /* Notification permission is requested exactly once (only while undecided)
     inside usePushNotifications — never re-requested after the user answers. */

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData({
      ...formData,
      [name]: type === "checkbox" ? checked : value,
    });
  };

  const handleTimeChange = (index, value) => {
    // For time inputs, prefer valueAsNumber for locale-independent 24h value
    let finalValue = value;
    setFormData((prev) => {
      const newTimes = [...prev.times];
      newTimes[index] = finalValue;
      return { ...prev, times: newTimes };
    });
  };

  /* Schedule is only a UI label — picking one does not overwrite times. */
  const handleScheduleChange = (e) => {
    const value = e.target.value;
    setFormData((prev) => ({
      ...prev,
      schedule: value,
    }));
  };

  /* ========== Save / Update Reminders (supports multiple times) ========== */
  const saveReminder = async () => {
    if (!formData.medicine_id) {
      showToast("error", "Please select a medicine");
      return;
    }

    // Validate schedule: only Morning / Afternoon / Evening / Night accepted
    if (formData.schedule && !SCHEDULE_OPTIONS.includes(formData.schedule)) {
      showToast(
        "error",
        "Invalid schedule. Choose Morning, Afternoon, Evening or Night."
      );
      return;
    }

    const validTimes = formData.times.filter((t) => t && t.trim());
    const expected = formData.frequencyDoses || 1;

    if (validTimes.length === 0) {
      showToast("error", `Please set at least one reminder time`);
      return;
    }

    if (validTimes.length !== expected) {
      showToast(
        "error",
        `Please set exactly ${expected} reminder time${expected > 1 ? "s" : ""} (you set ${validTimes.length})`
      );
      return;
    }

    // Check for duplicate times
    const uniqueTimes = new Set(validTimes.map((t) => normalizeTime24h(t)));
    if (uniqueTimes.size !== validTimes.length) {
      showToast("error", "Duplicate reminder times are not allowed");
      return;
    }

    setSaving(true);
    const reminderDate = formData.startDate || getLocalDateString();

    try {
      // Notification channel selection sent with every reminder so the
      // backend fires ONLY the channels the user picked (Push/Email/SMS).
      const channelFields = {
        notify_push: !!formData.push,
        notify_email: !!formData.email,
        notify_sms: !!formData.sms,
      };

      if (editId !== null && Array.isArray(editIds) && editIds.length > 0) {
        // ── EDIT MODE: update existing reminders ──
        const sorted = [...validTimes].sort();
        for (let i = 0; i < sorted.length; i++) {
          const time24 = normalizeTime24h(sorted[i]);
          if (i < editIds.length) {
            // Update existing reminder
            await api.patch(`reminders/${editIds[i]}/`, {
              reminder_time: time24,
              ...channelFields,
            });
          } else {
            // Create additional reminder (frequency increased)
            await api.post("reminders/", {
              medicine: formData.medicine_id,
              reminder_time: time24,
              reminder_date: reminderDate,
              status: "PENDING",
              is_recurring: formData.repeat === "Daily",
              recurring_interval: formData.repeat || "Daily",
              ...channelFields,
            });
          }
        }
        showToast("success", "Reminders updated successfully");
      } else {
        // ── CREATE MODE: create N new reminders ──
        const sorted = [...validTimes].sort();
        for (const timeStr of sorted) {
          await api.post("reminders/", {
            medicine: formData.medicine_id,
            reminder_time: normalizeTime24h(timeStr),
            reminder_date: reminderDate,
            status: "PENDING",
            is_recurring: formData.repeat === "Daily",
            recurring_interval: formData.repeat || "Daily",
            ...channelFields,
          });
        }
        showToast("success", `Reminders created successfully (${sorted.length} time${sorted.length > 1 ? "s" : ""})`);
      }

      await fetchData();
      setFormData(INITIAL_FORM);
      setEditId(null);
      setEditIds([]);
      setShowModal(false);
    } catch (error) {
      console.error("Reminder save error:", error.response?.status, error.response?.data);
      const status = error.response?.status;
      const responseData = error.response?.data;
      if (status === 401) {
        showToast("error", "Session expired. Please log in again.");
      } else if (status === 403) {
        showToast("error", "Permission denied. Please log in again.");
      } else {
        const msg =
          responseData?.medicine?.[0] ||
          responseData?.detail ||
          responseData?.non_field_errors?.[0] ||
          (typeof responseData === "object" ? JSON.stringify(responseData) : responseData) ||
          `Something went wrong (HTTP ${status || "network error"}). Please try again.`;
        showToast("error", msg);
      }
    } finally {
      setSaving(false);
    }
  };

  /* ========== Edit Reminders (loads all reminders for same medicine+date) ========== */
  const editReminder = (reminder) => {
    // Find ALL reminders for the same medicine on the same date
    const group = reminders
      .filter(
        (r) =>
          r.medicine === reminder.medicine &&
          r.reminder_date === reminder.reminder_date
      )
      .sort((a, b) => (a.reminder_time || "").localeCompare(b.reminder_time || ""));

    const med = medicinesList.find((m) => m.id === reminder.medicine);
    const freqDoses = med?.frequency_doses_per_day || group.length || 1;

    setEditId(reminder.id);
    setEditIds(group.map((r) => r.id));
    // Load the SAVED channel selection from the reminder (notify_push /
    // notify_email / notify_sms). Older reminders default to the previous
    // behaviour (push+email on, sms off).
    setFormData({
      medicine: getMedicineName(reminder.medicine),
      medicine_id: reminder.medicine,
      disease: reminder.disease || "",
      dosage: getMedicineDosage(reminder.medicine),
      times: group.map((r) => (r.reminder_time || "").substring(0, 5)),
      frequencyDoses: freqDoses,
      schedule: reminder.schedule || "",
      repeat: reminder.repeat || "Daily",
      startDate: reminder.reminder_date || "",
      endDate: reminder.endDate || "",
      push: reminder.notify_push !== undefined ? reminder.notify_push : true,
      email: reminder.notify_email !== undefined ? reminder.notify_email : true,
      sms: reminder.notify_sms !== undefined ? reminder.notify_sms : false,
      status: reminder.status || "Pending",
    });
    setShowModal(true);
  };

  /* ========== Delete Reminder ========== */
  const confirmDelete = (reminder) => {
    setDeleteTarget(reminder);
    setShowConfirm(true);
  };

  const executeDelete = async () => {
    if (!deleteTarget) return;
    setLoading(true);
    try {
      await api.delete(`reminders/${deleteTarget.id}/`);
      console.log("Reminder Deleted:", { id: deleteTarget.id });
      showToast("success", "Reminder deleted successfully");
      await fetchData();
    } catch (error) {
      console.error("Reminder delete error:", error.response?.status, error.response?.data);
      const status = error.response?.status;
      const detail = error.response?.data?.detail;
      if (status === 401) {
        showToast("error", "Session expired. Please log in again.");
      } else {
        showToast("error", detail || `Failed to delete reminder (HTTP ${status || "network error"})`);
      }
    } finally {
      setLoading(false);
      setShowConfirm(false);
      setDeleteTarget(null);
    }
  };

  /* ========== Export CSV ========== */
  const exportCSV = () => {
    const rows = [["Medicine", "Time", "Date", "Status"]];
    reminders.forEach((item) => {
      rows.push([
        getMedicineName(item.medicine),
        item.reminder_time || "",
        item.reminder_date || "",
        item.status || "",
      ]);
    });
    const csv = rows.map((e) => e.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "MedicationHistory.csv";
    a.click();
  };

  /* ========== Update status (Taken/Missed) via API ========== */
  const updateStatus = async (reminder, newStatus) => {
    setLoading(true);
    try {
      await api.patch(`reminders/${reminder.id}/`, { status: newStatus });
      showToast("success", `Reminder marked as ${newStatus}`);
      await fetchData();
    } catch (error) {
      console.error("Status update error:", error.response?.status, error.response?.data);
      const status = error.response?.status;
      const detail = error.response?.data?.detail;
      if (status === 401) {
        showToast("error", "Session expired. Please log in again.");
      } else {
        showToast("error", detail || `Failed to update status (HTTP ${status || "network error"})`);
      }
    } finally {
      setLoading(false);
    }
  };

  /* ========== Snooze Reminder (postpone by SNOOZE_MINUTES) ==========
     Uses the EXISTING backend snooze endpoint, which stores the SNOOZED
     status + snoozed_until and resets notification_sent (so the reminder can
     fire again after the snooze window). We also shift the saved
     reminder_date + reminder_time forward by SNOOZE_MINUTES so the
     exact-time scheduler re-fires at the new time. The scheduler effect
     re-activates SNOOZED reminders (status -> PENDING) once snoozed_until
     passes — this works without Celery. Because the schedule key
     (id|date|time) changes, duplicate-prevention and refresh-recovery
     keep working. */
  const SNOOZE_MINUTES = 10;

  const handleSnooze = async (reminder) => {
    const target = getTargetDate(reminder);
    if (!target) {
      showToast("error", "Cannot snooze: reminder has an invalid date or time");
      return;
    }
    setLoading(true);
    try {
      target.setMinutes(target.getMinutes() + SNOOZE_MINUTES);
      const pad = (n) => String(n).padStart(2, "0");
      const newDate = `${target.getFullYear()}-${pad(
        target.getMonth() + 1
      )}-${pad(target.getDate())}`;
      const newTime = `${pad(target.getHours())}:${pad(target.getMinutes())}`;

      // 1. Existing backend snooze logic: SNOOZED status + snoozed_until +
      //    notification_sent reset.
      await api.patch(`reminders/${reminder.id}/snooze/`, {
        minutes: SNOOZE_MINUTES,
      });

      // 2. Reschedule the stored date+time to the snoozed moment.
      await api.patch(`reminders/${reminder.id}/`, {
        reminder_date: newDate,
        reminder_time: newTime,
      });

      showToast(
        "success",
        `Snoozed — will remind again at ${formatTime12h(newTime)}`
      );
      await fetchData();
    } catch (error) {
      console.error("Snooze error:", error.response?.status, error.response?.data);
      const status = error.response?.status;
      const detail = error.response?.data?.detail;
      if (status === 401) {
        showToast("error", "Session expired. Please log in again.");
      } else {
        showToast("error", detail || `Failed to snooze reminder (HTTP ${status || "network error"})`);
      }
    } finally {
      setLoading(false);
    }
  };

  /* Re-activate a SNOOZED reminder once snoozed_until passes, so it becomes
     PENDING again and the exact-time scheduler fires it at its rescheduled
     time (exactly once). Without this, snoozed reminders would only
     re-activate when Celery Beat is running. */
  const reactivateReminder = useCallback(
    async (item) => {
      try {
        await api.patch(`reminders/${item.id}/`, {
          status: "PENDING",
          snoozed_until: null,
        });
        console.log("Snoozed Reminder Re-activated:", { id: item.id });
        await fetchData();
      } catch (error) {
        console.error("Failed to re-activate snoozed reminder:", error.response?.status, error.response?.data);
        const status = error.response?.status;
        const detail = error.response?.data?.detail;
        showToast("error", detail || `Failed to re-activate snoozed reminder (HTTP ${status || "error"})`);
      }
    },
    [fetchData, showToast]
  );

  /* ========== Compute stats ========== */
  const totalReminders = reminders.length;
  const takenCount = reminders.filter(
    (item) => item.status === "TAKEN" || item.status === "Taken"
  ).length;
  const adherence =
    totalReminders === 0
      ? 0
      : Math.round((takenCount / totalReminders) * 100);

  const pendingReminders = reminders.filter(
    (item) => item.status === "PENDING" || item.status === "Pending"
  );

  const nextReminder =
    pendingReminders.length > 0 ? pendingReminders[0] : null;

  const formatTime = (timeStr) => {
    if (!timeStr) return "--:--";
    return timeStr.substring(0, 5);
  };

  const [countdown, setCountdown] = useState("--:--:--");

  useEffect(() => {
    if (!nextReminder || !nextReminder.reminder_time) return;
    const timer = setInterval(() => {
      const now = new Date();
      const [hour, minute] = nextReminder.reminder_time.split(":");
      const target = new Date();
      target.setHours(Number(hour));
      target.setMinutes(Number(minute));
      target.setSeconds(0);
      let diff = target - now;
      if (diff < 0) diff += 24 * 60 * 60 * 1000;
      const h = String(Math.floor(diff / (1000 * 60 * 60))).padStart(2, "0");
      const m = String(Math.floor((diff / (1000 * 60)) % 60)).padStart(2, "0");
      const s = String(Math.floor((diff / 1000) % 60)).padStart(2, "0");
      setCountdown(`${h}:${m}:${s}`);
    }, 1000);
    return () => clearInterval(timer);
  }, [nextReminder]);

  /* Fire a reminder exactly once: shows the browser notification AND tells
     the backend to send the email + mark the reminder TRIGGERED at the exact
     same moment. The fired marker persists so it never fires again. */
  const fireReminder = useCallback(
    (item) => {
      const key = getReminderKey(item);
      // Exactly-once guards (in-session + persisted across refreshes)
      if (firedSessionRef.current.has(key)) return;
      if (isAlreadyFired(key)) return;
      firedSessionRef.current.add(key);

      const map = loadFiredMap();
      map[key] = new Date().toISOString();
      // Prune entries older than 30 days to keep storage bounded
      const cutoff = Date.now() - 30 * 24 * 60 * 60 * 1000;
      Object.keys(map).forEach((k) => {
        if (new Date(map[k]).getTime() < cutoff) delete map[k];
      });
      saveFiredMap(map);

      // Browser notification shows the same AM/PM formatting as the email
      console.log("Browser Notification Sent:", {
        medicine: getMedicineName(item.medicine),
        time: formatTime12h(item.reminder_time),
      });
      sendNotification(getMedicineName(item.medicine), formatTime12h(item.reminder_time));

      // Email + TRIGGERED must fire exactly with the browser notification.
      // POST /reminders/{id}/trigger/ executes the backend synchronously
      // (no Celery/Redis required). Fire-and-forget; the list catch-up on the
      // backend is the safety net if this request fails.
      api
        .post(`reminders/${item.id}/trigger/`)
        .then((res) => {
          const data = res.data || {};
          console.log("Email Sent / Reminder Completed:", { reminderId: item.id, backendStatus: data.status, emailSent: data.email_sent, data });
          // Reflect TRIGGERED status locally so the card updates immediately.
          // If the backend reports an email failure it keeps the reminder
          // PENDING for retry, so only flip to TRIGGERED when it succeeded.
          if (data.status === "triggered") {
            setReminders((prev) =>
              prev.map((r) =>
                r.id === item.id ? { ...r, status: "TRIGGERED" } : r
              )
            );
          }
        })
        .catch((err) => {
          console.error("Reminder trigger request failed:", err?.response?.data || err.message);
        });
    },
    [sendNotification, getMedicineName]
  );

  /* ==========================================================
     EXACT-TIME SCHEDULER (Improvement 1)
     - One setTimeout per pending reminder, scheduled for the
       exact saved date+time in the user's local timezone.
     - On edit/delete the reminders list changes → all timers are
       cleared and re-registered (old schedule cancelled).
     - Past/expired reminders are never scheduled.
     - Already-fired reminders (persisted in localStorage) are
       skipped so each reminder triggers exactly once.
     - Long horizons (> ~24 days) are re-chunked so setTimeout
       never overflows its max delay.
  ========================================================== */
  useEffect(() => {
    Object.values(timersRef.current).forEach(clearTimeout);
    timersRef.current = {};

    const now = Date.now();
    console.log("Scheduler Started:", { currentDateTime: new Date(now).toString() });
    reminders.forEach((item) => {
      const status = (item.status || "").toUpperCase();

      // SNOOZED reminders: schedule a re-activation at snoozed_until so the
      // reminder becomes actionable again (works without Celery Beat). Once
      // re-activated to PENDING, the scheduler below fires it at its
      // rescheduled time — exactly once, thanks to the fired-key guards.
      if (status === "SNOOZED") {
        const snoozeEnd = item.snoozed_until
          ? new Date(item.snoozed_until)
          : getTargetDate(item);
        const delayMs = snoozeEnd ? snoozeEnd.getTime() - now : 0;
        if (snoozeEnd && delayMs > 0) {
          console.log("Snoozed Reminder Scheduled for re-activation:", {
            id: item.id,
            snoozedUntil: snoozeEnd.toString(),
          });
          const armReactivation = () => {
            const remaining = snoozeEnd.getTime() - Date.now();
            if (remaining <= 0) {
              delete timersRef.current[item.id];
              reactivateReminder(item);
              return;
            }
            const chunk = Math.min(remaining, MAX_TIMEOUT_DELAY);
            timersRef.current[item.id] = setTimeout(
              armReactivation,
              chunk
            );
          };
          armReactivation();
        } else {
          console.log("Reminder Skipped:", {
            id: item.id,
            reason: "snoozed without a future snoozed_until",
          });
        }
        return;
      }

      if (status !== "PENDING") {
        console.log("Reminder Skipped:", { id: item.id, reason: `status=${item.status}` });
        return; // only pending reminders fire
      }
      const target = getTargetDate(item);
      if (!target) {
        console.log("Reminder Skipped:", { id: item.id, reason: "invalid date/time" });
        return; // invalid/legacy date+time — never fires
      }

      let delay = target.getTime() - now;
      if (delay <= 0) {
        console.log("Reminder Skipped:", { id: item.id, reason: "past due" });
        return; // expired reminder — never fires again
      }

      const key = getReminderKey(item);
      if (firedSessionRef.current.has(key) || isAlreadyFired(key)) {
        console.log("Reminder Skipped:", { id: item.id, reason: "already fired" });
        return;
      }

      scheduledKeysRef.current.add(key);

      console.log("Reminder Scheduled:", {
        id: item.id,
        targetDateTime: target.toString(),
        currentDateTime: new Date(now).toString(),
        millisecondsRemaining: delay,
      });

      const arm = () => {
        delay = target.getTime() - Date.now();
        if (delay <= 0) {
          delete timersRef.current[item.id];
          console.log("Scheduler Triggered:", { id: item.id, targetDateTime: target.toString() });
          fireReminder(item);
          return;
        }
        const chunk = Math.min(delay, MAX_TIMEOUT_DELAY);
        console.log("Reminder Rescheduled:", { id: item.id, millisecondsRemaining: delay });
        timersRef.current[item.id] = setTimeout(arm, chunk);
      };
      arm();
    });

    return () => {
      Object.values(timersRef.current).forEach(clearTimeout);
      console.log("Reminder Cancelled:", { clearedTimers: Object.keys(timersRef.current).length });
      timersRef.current = {};
    };
  }, [reminders, fireReminder, reactivateReminder]);

  /* Catch-up safety net: fires reminders that became due while the
     tab was backgrounded (timers throttled) — still exactly-once.
     Reminders that were already past on page load are never fired. */
  const runCatchUp = useCallback(() => {
    const now = Date.now();
    reminders.forEach((item) => {
      const status = (item.status || "").toUpperCase();
      if (status !== "PENDING") return;
      const target = getTargetDate(item);
      if (!target || target.getTime() > now) return;
      const key = getReminderKey(item);
      if (!scheduledKeysRef.current.has(key)) return; // past on load
      if (firedSessionRef.current.has(key) || isAlreadyFired(key)) return;
      fireReminder(item);
    });
  }, [reminders, fireReminder]);

  useEffect(() => {
    const interval = setInterval(runCatchUp, 30000);
    const onVisibility = () => {
      if (!document.hidden) runCatchUp();
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [runCatchUp]);

  if (pageLoading) {
    return (
      <>
        <Navbar />
        <div className="loading-overlay">
          <div className="loading-spinner">
            <FaSpinner className="spinner-icon" />
            <p>Loading reminders...</p>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <Navbar />

      {/* Toast Messages */}
      {message.text && (
        <div className={`message-toast ${message.type}`}>
          {message.type === "success" ? (
            <FaCheckCircle />
          ) : message.type === "error" ? (
            <FaExclamationCircle />
          ) : (
            <FaExclamationTriangle />
          )}
          {message.text}
        </div>
      )}

      {/* Loading Overlay */}
      {(loading || saving) && (
        <div className="loading-overlay">
          <div className="loading-spinner">
            <FaSpinner className="spinner-icon" />
            <p>{saving ? "Saving..." : "Processing..."}</p>
          </div>
        </div>
      )}

      <div className="reminder-page">
        {/* Header */}
        <div className="reminder-header">
          <div>
            <h1>Reminder System</h1>
            <p>Manage all medicine reminders</p>
          </div>
          <div style={{ display: "flex", gap: "10px" }}>
            <button
              className="add-btn"
              style={{ background: "#ffffff", color: "#0D766E", border: "1.5px solid #0D766E" }}
              onClick={testPush}
              disabled={testingPush}
              title="Send a real test push notification to this browser"
            >
              <FaBell />
              {testingPush ? "Sending..." : "Test Push"}
            </button>
            <button
              className="add-btn"
              onClick={() => {
                setFormData(INITIAL_FORM);
                setEditId(null);
                setEditIds([]);
                setShowModal(true);
              }}
            >
              <FaPlus />
              Add Reminder
            </button>
          </div>
        </div>

        {/* ── Notification channel status banner (honest status only) ── */}
        {pushReady === false && (
          <div
            className="message-toast warning"
            style={{ position: "static", transform: "none", marginBottom: 16, zIndex: 1 }}
          >
            <FaExclamationTriangle />
            Push notifications are OFF for this browser. Click the lock icon in the address bar →
            Site settings → Notifications → Allow, then reload. Use “Test Push” to verify.
          </div>
        )}
        {emailConfig && !emailConfig.configured && (
          <div
            className="message-toast warning"
            style={{ position: "static", transform: "none", marginBottom: 16, zIndex: 1 }}
          >
            <FaExclamationTriangle />
            Email notifications are not configured on the server
            {emailConfig.missing?.length ? ` (missing: ${emailConfig.missing.join(", ")})` : ""}
            . Set EMAIL_HOST / EMAIL_HOST_USER / EMAIL_HOST_PASSWORD in backend/.env.
          </div>
        )}

        {/* Today's Summary */}
        <div className="summary-grid">
          <div className="summary-card">
            <h3>Total Reminders</h3>
            <h1>{reminders.length}</h1>
          </div>
          <div className="summary-card">
            <h3>Pending</h3>
            <h1>{pendingReminders.length}</h1>
          </div>
          <div className="summary-card">
            <h3>Taken</h3>
            <h1>{takenCount}</h1>
          </div>
        </div>

        {/* Next Dose Countdown */}
        <div className="countdown-card">
          <div className="countdown-left">
            <div className="countdown-icon">⏳</div>
            <div>
              <h2>Next Dose</h2>
              <h3>
                {nextReminder
                  ? getMedicineName(nextReminder.medicine)
                  : "No Reminder"}
              </h3>
              <p>
                <span>🕒 {formatTime(nextReminder?.reminder_time)}</span>
                <span>📅 {nextReminder?.reminder_date}</span>
              </p>
            </div>
          </div>
          <div className="countdown-right">
            <h1>{countdown}</h1>
            <p>Remaining</p>
          </div>
        </div>

        {/* Medication Adherence */}
        <div className="adherence-card">
          <div className="adherence-top">
            <h2>Medication Adherence</h2>
            <h1>{adherence}%</h1>
          </div>
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${adherence}%` }}
            ></div>
          </div>
          <p>
            {takenCount} of {totalReminders} reminders completed
          </p>
        </div>

        {/* Reminder Cards */}
        <div className="reminder-grid">
          {reminders.length === 0 ? (
            <div className="empty">
              <h2>No Reminder Added</h2>
              <p>Click on Add Reminder to create your first reminder</p>
            </div>
          ) : (
            reminders.map((item) => (
              <div className="reminder-card" key={item.id}>
                <div className="card-top">
                  <div>
                    <h2>{getMedicineName(item.medicine)}</h2>
                    <p>
                      <b>Dosage :</b> {getMedicineDosage(item.medicine)}
                    </p>
                    <p>{item.schedule || ""}</p>
                  </div>
                  <FaBell className="bell" />
                </div>

                <div className="time">
                  <FaClock />
                  <span>{formatTime(item.reminder_time)}</span>
                </div>

                <div className="info">
                  <p>
                    Date : <b>{item.reminder_date}</b>
                  </p>
                  <p>
                    Status :
                    <b> {item.status}</b>
                  </p>
                </div>

                <div className="notify">
                  {/* Show the channels SAVED on this reminder */}
                  {item.notify_push && <span>🔔 Push</span>}
                  {item.notify_email && <span>✉️ Email</span>}
                  {item.notify_sms && <span>📱 SMS</span>}
                  {!item.notify_push && !item.notify_email && !item.notify_sms && (
                    <span>🔕 None</span>
                  )}
                </div>

                <div className="actions">
                  <button
                    className="taken-btn"
                    onClick={() => updateStatus(item, "TAKEN")}
                    disabled={loading}
                  >
                    Taken
                  </button>
                  <button
                    className="missed-btn"
                    onClick={() => updateStatus(item, "MISSED")}
                    disabled={loading}
                  >
                    Missed
                  </button>
                  <button
                    className="snooze-btn"
                    onClick={() => handleSnooze(item)}
                    disabled={loading}
                  >
                    Snooze
                  </button>
                  <FaEdit
                    className="icon"
                    onClick={() => editReminder(item)}
                  />
                  <FaTrash
                    className="icon delete"
                    onClick={() => confirmDelete(item)}
                  />
                </div>
              </div>
            ))
          )}
        </div>

        {/* Upcoming Notifications */}
        <div className="notification-panel">
          <h2>Upcoming Notifications</h2>
          {pendingReminders.length === 0 ? (
            <p>No Upcoming Notifications</p>
          ) : (
            pendingReminders.map((item) => (
              <div key={item.id} className="notification-card">
                <div>
                  <h3>{getMedicineName(item.medicine)}</h3>
                  <p>{formatTime(item.reminder_time)}</p>
                </div>
                <span>{item.reminder_date}</span>
              </div>
            ))
          )}
        </div>

        {/* Reminder History */}
        <div className="history">
          <div className="history-top">
            <h2>Reminder History</h2>
            <button className="export-btn" onClick={exportCSV}>
              Export CSV
            </button>
          </div>
          <table>
            <thead>
              <tr>
                <th>Medicine</th>
                <th>Time</th>
                <th>Date</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {reminders.map((item) => (
                <tr key={item.id}>
                  <td>{getMedicineName(item.medicine)}</td>
                  <td>{formatTime(item.reminder_time)}</td>
                  <td>{item.reminder_date}</td>
                  <td>
                    <span
                      className={`status ${(item.status || "").toLowerCase()}`}
                    >
                      {item.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add / Edit Reminder Modal (Compact) */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <h2>{editId !== null ? "Edit Reminder" : "Add Reminder"}</h2>

            <select
              name="medicine"
              value={formData.medicine}
              disabled={editId !== null}
              onChange={(e) => {
                const selected = medicinesList.find(
                  (item) => item.medicine_name === e.target.value
                );
                if (selected) {
                  const freq = selected.frequency || "";
                  const validFreq = SCHEDULE_OPTIONS.includes(freq)
                    ? freq
                    : formData.schedule;
                  const freqDoses = selected.frequency_doses_per_day || 1;
                  setFormData({
                    ...formData,
                    medicine: selected.medicine_name,
                    medicine_id: selected.id,
                    dosage: selected.dosage || "",
                    schedule: validFreq,
                    frequencyDoses: freqDoses,
                    times: Array(freqDoses).fill(""),
                  });
                }
              }}
            >
              <option value="">Select Medicine</option>
              {medicinesList.map((item) => (
                <option key={item.id} value={item.medicine_name}>
                  {item.medicine_name}
                </option>
              ))}
            </select>

            <input
              type="text"
              value={formData.disease}
              placeholder="Disease (optional)"
              name="disease"
              onChange={handleChange}
            />

            <div className="form-row">
              <input
                type="text"
                value={formData.dosage}
                placeholder="Dosage (auto-filled)"
                readOnly
              />
            </div>

            {/* ── Dynamic reminder times based on medicine frequency ── */}
            <div className="reminder-times-section" style={{ margin: "12px 0" }}>
              <p style={{ fontSize: "13px", color: "#0F766E", fontWeight: 600, marginBottom: 8 }}>
                Reminder Times ({formData.times.filter((t) => t).length} of {formData.frequencyDoses} set)
              </p>
              {formData.times.map((time, index) => (
                <div key={index} className="form-row" style={{ marginBottom: 8 }}>
                  <label style={{ fontSize: "13px", color: "#475569", fontWeight: 500, minWidth: 60 }}>
                    Time {index + 1}
                  </label>
                  <input
                    type="time"
                    value={time}
                    onChange={(e) => handleTimeChange(index, e.target.value)}
                    required
                  />
                </div>
              ))}
              {formData.frequencyDoses === 0 && (
                <p style={{ fontSize: "12px", color: "#94a3b8" }}>
                  Select a medicine to see reminder time fields
                </p>
              )}
            </div>

            <div className="form-row">
              <select
                name="schedule"
                value={formData.schedule}
                onChange={handleScheduleChange}
              >
                <option value="">Schedule</option>
                {SCHEDULE_OPTIONS.map((opt) => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </select>
              <select
                name="repeat"
                value={formData.repeat}
                onChange={handleChange}
              >
                <option value="Daily">Daily</option>
                <option value="Weekly">Weekly</option>
                <option value="Monthly">Monthly</option>
              </select>
            </div>

            <div className="form-row">
              <input
                type="date"
                name="startDate"
                value={formData.startDate}
                onChange={handleChange}
                placeholder="Start Date"
              />
              <input
                type="date"
                name="endDate"
                value={formData.endDate}
                onChange={handleChange}
                placeholder="End Date"
              />
            </div>

            <h3>Notification</h3>
            <div className="notify-grid">
              <label>
                <input
                  type="checkbox"
                  name="push"
                  checked={formData.push}
                  onChange={handleChange}
                />
                Push
              </label>
              <label>
                <input
                  type="checkbox"
                  name="email"
                  checked={formData.email}
                  onChange={handleChange}
                />
                Email
              </label>
              <label>
                <input
                  type="checkbox"
                  name="sms"
                  checked={formData.sms}
                  onChange={handleChange}
                />
                SMS
              </label>
            </div>

            <div className="modal-buttons">
              <button onClick={() => setShowModal(false)} disabled={saving}>
                Cancel
              </button>
              <button onClick={saveReminder} disabled={saving}>
                {saving ? (
                  <>
                    <FaSpinner style={{ marginRight: 6 }} /> Saving...
                  </>
                ) : editId !== null ? (
                  "Update Reminder"
                ) : (
                  "Save Reminder"
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showConfirm && deleteTarget && (
        <div className="confirm-overlay" onClick={() => setShowConfirm(false)}>
          <div className="confirm-box" onClick={(e) => e.stopPropagation()}>
            <div className="confirm-icon">
              <FaExclamationTriangle />
            </div>
            <h3>Delete Reminder</h3>
            <p>
              Are you sure you want to delete the reminder for{" "}
              <strong>{getMedicineName(deleteTarget.medicine)}</strong>?
            </p>
            <div className="confirm-buttons">
              <button
                className="btn-cancel"
                onClick={() => {
                  setShowConfirm(false);
                  setDeleteTarget(null);
                }}
              >
                Cancel
              </button>
              <button className="btn-delete" onClick={executeDelete}>
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default Reminders;
