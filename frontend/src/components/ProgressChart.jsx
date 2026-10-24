import { useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

import "../styles/Chart.css";

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

// Local timezone date string (YYYY-MM-DD) — matches how reminder_date is
// created and stored on the frontend/backend.
const toLocalDateString = (date) => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
};

// Monday-first list of the 7 dates in the current week.
const getCurrentWeekDates = () => {
  const today = new Date();
  const mondayOffset = (today.getDay() + 6) % 7; // 0 = Monday
  const monday = new Date(
    today.getFullYear(),
    today.getMonth(),
    today.getDate() - mondayOffset
  );
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    return d;
  });
};

// Real daily adherence for the current week, derived entirely from the
// user's reminder records: (taken / scheduled) × 100 for each day.
function ProgressChart({ reminders = [], medicines = [], loading = false, error = null }) {
  // Compute expected daily doses from active medicines' frequency field.
  const expectedDailyDoses = useMemo(
    () => medicines
      .filter((m) => m.is_active !== false)
      .reduce((sum, m) => sum + (m.frequency_doses_per_day || 1), 0),
    [medicines]
  );

  const data = useMemo(() => {
    const weekDates = getCurrentWeekDates();
    return weekDates.map((date, idx) => {
      const dateStr = toLocalDateString(date);
      const dayReminders = reminders.filter((r) => r.reminder_date === dateStr);
      const taken = dayReminders.filter((r) => r.status === "TAKEN").length;
      // Use frequency-based expected doses when available.
      const expected = expectedDailyDoses > 0 ? expectedDailyDoses : dayReminders.length;
      return {
        day: DAY_LABELS[idx],
        score: expected > 0 ? Math.round((taken / expected) * 100) : 0,
        total: expected,
      };
    });
  }, [reminders, expectedDailyDoses]);

  // The chart must never pretend real data exists: an API failure renders a
  // clear error state, a first load shows a loading state, and a genuinely
  // empty week shows an empty state — never a fabricated all-zero line.
  const hasWeekData = data.some((d) => d.total > 0);

  if (error) {
    return (
      <div className="chartCard">
        <h2>Adherence Progress</h2>
        <div className="chart-state-msg">
          <p>Couldn't load your adherence data.</p>
          <p>Check your connection and try again.</p>
        </div>
      </div>
    );
  }

  if (loading && !hasWeekData) {
    return (
      <div className="chartCard">
        <h2>Adherence Progress</h2>
        <div className="chart-state-msg">
          <p>Loading your adherence data…</p>
        </div>
      </div>
    );
  }

  if (!hasWeekData) {
    return (
      <div className="chartCard">
        <h2>Adherence Progress</h2>
        <div className="chart-state-msg">
          <p>No medication reminders this week yet.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="chartCard">

      <h2>Adherence Progress</h2>

      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data}>

          <CartesianGrid strokeDasharray="3 3" />

          <XAxis dataKey="day" />

          <YAxis />

          <Tooltip />

          <Line
            type="monotone"
            dataKey="score"
            stroke="#00897B"
            strokeWidth={4}
          />

        </LineChart>
      </ResponsiveContainer>

    </div>
  );
}

export default ProgressChart;
