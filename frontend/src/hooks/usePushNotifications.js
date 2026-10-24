import { useEffect, useRef, useState } from "react";
import api from "../services/api";

/**
 * REAL Web Push notifications hook.
 *
 * Flow (all automatic on login/pages using this hook):
 * 1. Register /sw.js service worker.
 * 2. Request browser Notification permission (only while "default").
 * 3. If granted, create a PushSubscription with the backend's VAPID
 *    public key (GET /reminders/push/vapid-key/).
 * 4. POST the subscription to /reminders/push/subscribe/ so the backend
 *    can deliver REAL push messages via pywebpush when reminders fire.
 * 5. Also poll GET /reminders/notification-logs/pending-push/ as an
 *    in-app fallback so users still see reminders in-app.
 *
 * The actual OS notification is shown by the service worker's "push"
 * event handler in public/sw.js.
 *
 * Returns the push readiness state so pages can show an HONEST status:
 *   undefined = still checking, true = subscribed & ready,
 *   false = unavailable/denied/failed (user action required).
 */
function usePushNotifications() {
  const seenIdsRef = useRef(new Set());
  const subscribedRef = useRef(false);
  const [pushReady, setPushReady] = useState(undefined);

  useEffect(() => {
    let cancelled = false;

    /* ── 1+2: SW registration + permission ─────────────────────────── */
    const setupPush = async () => {
      try {
        const token = localStorage.getItem("access");
        if (!token) return; // Not logged in — nothing to subscribe.

        if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
          console.info("[Push] Push messaging not supported in this browser.");
          setPushReady(false);
          return;
        }

        const registration = await navigator.serviceWorker.register("/sw.js");
        await navigator.serviceWorker.ready;

        // Ask for permission only while the user hasn't decided yet.
        if (!("Notification" in window)) {
          setPushReady(false);
          return;
        }
        if (Notification.permission === "denied") {
          console.info("[Push] Notification permission was denied by the user.");
          setPushReady(false);
          return;
        }
        if (Notification.permission === "default") {
          const result = await Notification.requestPermission();
          if (result !== "granted") {
            setPushReady(false);
            return;
          }
        }

        /* ── 3: Get the backend's VAPID public key ── */
        const keyRes = await api.get("reminders/push/vapid-key/");
        const publicKey = keyRes.data?.publicKey;
        if (!publicKey) {
          console.warn("[Push] Backend did not return a VAPID public key.");
          setPushReady(false);
          return;
        }

        // Convert base64url VAPID key -> Uint8Array (browser requirement).
        const urlBase64ToUint8Array = (base64String) => {
          const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
          const base64 = (base64String + padding)
            .replace(/-/g, "+")
            .replace(/_/g, "/");
          const raw = window.atob(base64);
          const output = new Uint8Array(raw.length);
          for (let i = 0; i < raw.length; i += 1) {
            output[i] = raw.charCodeAt(i);
          }
          return output;
        };

        /* ── Create (or reuse) the PushSubscription ── */
        let subscription = await registration.pushManager.getSubscription();
        if (!subscription) {
          subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(publicKey),
          });
        }

        /* ── 4: Send it to the backend ── */
        const subJson = subscription.toJSON();
        await api.post("reminders/push/subscribe/", {
          endpoint: subJson.endpoint,
          keys: subJson.keys,
          user_agent: navigator.userAgent.slice(0, 255),
        });
        subscribedRef.current = true;
        setPushReady(true);
        console.info("[Push] Subscription stored — real push is active.");
      } catch (err) {
        // Never crash the host page; just report for debugging.
        const status = err?.response?.status;
        const detail = err?.response?.data?.detail || err?.message;
        console.warn(
          `[Push] setup failed${status ? ` (HTTP ${status})` : ""}: ${detail}`
        );
        setPushReady(false);
      }
    };

    /* ── 5: Polling fallback (in-app + page notifications) ─────────── */
    const fetchAndNotify = async () => {
      try {
        const token = localStorage.getItem("access");
        if (!token) return; // Not logged in — skip silently.

        const res = await api.get("reminders/notification-logs/pending-push/");
        const notifications = Array.isArray(res.data) ? res.data : [];

        for (const notif of notifications) {
          // Skip notifications we've already shown this session.
          if (seenIdsRef.current.has(notif.id)) continue;
          seenIdsRef.current.add(notif.id);

          // Page-level fallback notification (only when the page is open;
          // real background push is delivered by the service worker).
          if (
            "Notification" in window &&
            Notification.permission === "granted" &&
            document.visibilityState === "visible"
          ) {
            try {
              new Notification(notif.title || "Medicine Reminder", {
                body: notif.body || "Time to take your medicine.",
                icon: "/favicon.svg",
                tag: `pillsync-poll-${notif.id}`,
              });
            } catch {
              // Notification constructor can throw in some environments.
            }
          }
        }

        // Prune seen IDs to prevent memory growth over long sessions.
        if (seenIdsRef.current.size > 500) {
          const ids = Array.from(seenIdsRef.current);
          seenIdsRef.current = new Set(ids.slice(-250));
        }
      } catch {
        // Silently ignore poll failures — never crash the host component.
      }
    };

    setupPush();
    const initialTimeout = setTimeout(fetchAndNotify, 2000);
    const intervalId = setInterval(fetchAndNotify, 15000);

    return () => {
      cancelled = true;
      clearTimeout(initialTimeout);
      clearInterval(intervalId);
    };
  }, []);

  return pushReady;
}

export default usePushNotifications;
