import { useMemo } from "react";
import "../styles/Chart.css";

// Real activity types derived from reminder statuses.
const STATUS_ACTIVITY = {
  TAKEN: { icon: "✔", label: "Taken", color: "#16a34a" },
  MISSED: { icon: "✘", label: "Missed", color: "#dc2626" },
  SNOOZED: { icon: "⏰", label: "Snoozed", color: "#d97706" },
};

const formatTime = (ts) => {
  if (!ts) return "";
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

// Recent Activity is built entirely from the user's real records:
//   1. Reminder status changes (Taken / Missed / Snoozed) — timestamped with
//      the reminder's updated_at.
//   2. Notification logs (each reminder firing is recorded in NotificationLog)
//      — "Reminder Completed", deduped per reminder, timestamped with created_at.
// Newest activities are shown first.
function RecentActivity({
  reminders = [],
  medicines = [],
  notificationLogs = [],
}) {
  const activities = useMemo(() => {
    const getMedicineName = (id) => {
      const med = medicines.find((m) => m.id === id);
      return med ? med.medicine_name : `Medicine #${id}`;
    };

    const items = [];

    // Status changes → Medicine Taken / Missed / Snoozed
    const statusReminderIds = new Set();
    reminders.forEach((r) => {
      const meta = STATUS_ACTIVITY[r.status];
      if (!meta) return;
      statusReminderIds.add(r.id);
      items.push({
        id: `reminder-${r.id}`,
        icon: meta.icon,
        color: meta.color,
        text: `${getMedicineName(r.medicine)} ${meta.label}`,
        time: r.updated_at,
      });
    });

    // Notification logs → Reminder Completed (one entry per reminder firing).
    // Skip reminders that already have a status-based entry above, so one
    // medicine never produces duplicate activities.
    const seenReminders = new Set();
    notificationLogs
      .slice()
      .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
      .forEach((log) => {
        if (log.status !== "SENT") return;
        const details = log.reminder_details || {};
        if (details.id === undefined) return;
        if (statusReminderIds.has(details.id)) return;
        if (seenReminders.has(details.id)) return;
        seenReminders.add(details.id);
        items.push({
          id: `log-${log.id}`,
          icon: "🔔",
          color: "#2563eb",
          text: `${details.medicine || "Medication"} Reminder Completed`,
          time: log.created_at,
        });
      });

    return items
      .sort((a, b) => new Date(b.time) - new Date(a.time))
      .slice(0, 6);
  }, [reminders, medicines, notificationLogs]);

  return (
    <div className="activityCard">
      <h2>Recent Activity</h2>
      {activities.length > 0 ? (
        <ul>
          {activities.map((act) => (
            <li key={act.id}>
              <span style={{ color: act.color, marginRight: 8 }}>{act.icon}</span>
              {act.text}
              {act.time ? (
                <span style={{ float: "right", color: "#94a3b8", fontSize: 13 }}>
                  {formatTime(act.time)}
                </span>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p style={{ color: "#94a3b8", textAlign: "center", padding: "15px 0" }}>
          No recent activity yet
        </p>
      )}
    </div>
  );
}

export default RecentActivity;
