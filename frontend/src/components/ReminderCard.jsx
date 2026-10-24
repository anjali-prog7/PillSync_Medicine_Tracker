import { useMemo } from "react";
import "../styles/Chart.css";

const formatTime12h = (timeStr) => {
  if (!timeStr) return "--:--";
  const parts = String(timeStr).split(":");
  const hour = Number(parts[0]);
  const minute = Number(parts[1]);
  if (Number.isNaN(hour) || Number.isNaN(minute)) return timeStr;
  const suffix = hour >= 12 ? "PM" : "AM";
  const hour12 = hour % 12 || 12;
  return `${hour12}:${String(minute).padStart(2, "0")} ${suffix}`;
};

const STATUS_META = {
  PENDING: { label: "Pending", color: "#d97706", bg: "#fef3c7" },
  TRIGGERED: { label: "Triggered", color: "#7c3aed", bg: "#ede9fe" },
  TAKEN: { label: "Taken", color: "#16a34a", bg: "#d1fae5" },
  MISSED: { label: "Missed", color: "#dc2626", bg: "#fee2e2" },
  SNOOZED: { label: "Snoozed", color: "#2563eb", bg: "#dbeafe" },
};

// Today's Reminders — fetched from the backend and filtered to the current
// local date, showing medicine name, scheduled time, and current status.
function ReminderCard({ reminders = [], medicines = [] }) {
  const todayReminders = useMemo(() => {
    const now = new Date();
    const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(
      2,
      "0"
    )}-${String(now.getDate()).padStart(2, "0")}`;

    const getMedicineName = (id) => {
      const med = medicines.find((m) => m.id === id);
      return med ? med.medicine_name : `Medicine #${id}`;
    };

    return reminders
      .filter((r) => r.reminder_date === today)
      .sort((a, b) =>
        (a.reminder_time || "").localeCompare(b.reminder_time || "")
      )
      .map((r) => ({
        id: r.id,
        name: getMedicineName(r.medicine),
        time: formatTime12h(r.reminder_time),
        status:
          STATUS_META[r.status] || {
            label: r.status || "Pending",
            color: "#64748b",
            bg: "#f1f5f9",
          },
      }));
  }, [reminders, medicines]);

  return (
    <div className="activityCard">
      <h2>Today's Reminders</h2>
      {todayReminders.length > 0 ? (
        <ul>
          {todayReminders.map((r) => (
            <li key={r.id}>
              <span>
                {r.time} - {r.name}
              </span>
              <span
                style={{
                  float: "right",
                  fontSize: 12,
                  fontWeight: 600,
                  padding: "2px 10px",
                  borderRadius: 10,
                  background: r.status.bg,
                  color: r.status.color,
                }}
              >
                {r.status.label}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p style={{ color: "#94a3b8", textAlign: "center", padding: "15px 0" }}>
          No reminders for today 🎉
        </p>
      )}
    </div>
  );
}

export default ReminderCard;
