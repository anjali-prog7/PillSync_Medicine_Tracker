import { useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  Legend,
  AreaChart,
  Area,
} from "recharts";
import { FaChartBar, FaChartLine, FaChartPie, FaArrowUp, FaArrowDown, FaMinus } from "react-icons/fa";
import "../styles/DashboardAnalytics.css";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

// Local-timezone date key (YYYY-MM-DD) for a Date. `reminder_date` is stored
// as the user's local wall-clock date, so it must NEVER be derived via
// toISOString() (which converts to UTC and can shift a reminder to another
// day in any timezone east of UTC before ~05:30 or west of UTC in the evening).
const toDateKey = (date) => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
};

// Time-slot buckets (same convention as the Adherence Tracker):
// Morning 05:00-11:59 · Afternoon 12:00-16:59 · Evening 17:00-20:59 · Night 21:00-04:59
const getTimeSlot = (timeStr) => {
  if (!timeStr) return "Night";
  const [h] = timeStr.split(":").map(Number);
  if (h >= 5 && h < 12) return "Morning";
  if (h >= 12 && h < 17) return "Afternoon";
  if (h >= 17 && h < 21) return "Evening";
  return "Night";
};

function DashboardAnalytics({ reminders = [], medicines = [] }) {
  const now = new Date();
  const today = now.toISOString().split("T")[0];

  const getDayIndex = (dateStr) => {
    return new Date(dateStr).getDay();
  };

  const getWeekNumber = (dateStr) => {
    const d = new Date(dateStr);
    const startOfYear = new Date(d.getFullYear(), 0, 1);
    const diff = d.getTime() - startOfYear.getTime();
    return Math.ceil((diff / (1000 * 60 * 60 * 24) + startOfYear.getDay() + 1) / 7);
  };

  // Compute expected daily doses from active medicines' frequency field.
  const activeMedicines = useMemo(
    () => medicines.filter((m) => m.is_active !== false),
    [medicines]
  );
  const expectedDailyDoses = useMemo(
    () => activeMedicines.reduce((sum, m) => sum + (m.frequency_doses_per_day || 1), 0),
    [activeMedicines]
  );

  const weeklyReport = useMemo(() => {
    const currentWeek = getWeekNumber(today);
    const currentYear = now.getFullYear();
    const weekReminders = reminders.filter((r) => {
      const d = new Date(r.reminder_date);
      return getWeekNumber(r.reminder_date) === currentWeek && d.getFullYear() === currentYear;
    });
    return DAYS.map((day, idx) => {
      const dayReminders = weekReminders.filter((r) => getDayIndex(r.reminder_date) === idx);
      return {
        day,
        taken: dayReminders.filter((r) => r.status === "TAKEN").length,
        missed: dayReminders.filter((r) => r.status === "MISSED").length,
        pending: dayReminders.filter((r) => r.status === "PENDING").length,
      };
    });
  }, [reminders, today, now]);

  const monthlyReport = useMemo(() => {
    const currentMonth = now.getMonth();
    const currentYear = now.getFullYear();
    const months = [];
    for (let i = 5; i >= 0; i--) {
      let monthIdx = currentMonth - i;
      let year = currentYear;
      if (monthIdx < 0) { monthIdx += 12; year -= 1; }
      const monthReminders = reminders.filter((r) => {
        const d = new Date(r.reminder_date);
        return d.getMonth() === monthIdx && d.getFullYear() === year;
      });
      const taken = monthReminders.filter((r) => r.status === "TAKEN").length;
      // Use frequency-based expected doses for adherence calculation.
      // Compute the number of unique days with reminders in this month.
      const uniqueDays = new Set(monthReminders.map((r) => r.reminder_date)).size;
      const expectedMonthDoses = expectedDailyDoses > 0 ? expectedDailyDoses * uniqueDays : monthReminders.length;
      months.push({
        month: MONTHS[monthIdx],
        adherence: expectedMonthDoses > 0 ? Math.round((taken / expectedMonthDoses) * 100) : 0,
        taken,
        missed: monthReminders.filter((r) => r.status === "MISSED").length,
      });
    }
    return months;
  }, [reminders, now, expectedDailyDoses]);

  const missedAnalysis = useMemo(() => {
    // ONLY genuinely missed reminders count. TAKEN / PENDING / TRIGGERED /
    // SNOOZED reminders are never treated as missed here.
    const missed = reminders.filter((r) => r.status === "MISSED");
    return ["Morning", "Afternoon", "Evening", "Night"].map((slot) => ({
      name: slot,
      value: missed.filter((r) => getTimeSlot(r.reminder_time) === slot).length,
    }));
  }, [reminders]);

  const totalMissed = missedAnalysis.reduce((sum, d) => sum + d.value, 0);
  const hasMissedData = totalMissed > 0;

  // Only time slots that actually contain missed doses are drawn — zero-value
  // slots are dropped from the donut AND the legend so they never visually
  // dominate (e.g. a single Night miss renders as one clear colored segment,
  // not a mostly-grey ring). The center total and tooltip still show real
  // counts computed from the reminders data.
  const missedPieData = missedAnalysis.filter((d) => d.value > 0);

  // Real daily adherence over the last 30 days, built from the actual reminder
  // history returned by GET /api/reminders/ (the logged-in user's reminders
  // only). Days without any reminder records are skipped so the chart never
  // invents dates. Adherence % = taken / total * 100 per day — matching the
  // Adherence Score convention already used across the dashboard.
  const adherenceTrend = useMemo(() => {
    const data = [];
    const nowLocal = new Date();
    for (let i = 29; i >= 0; i--) {
      const d = new Date(
        nowLocal.getFullYear(),
        nowLocal.getMonth(),
        nowLocal.getDate()
      );
      d.setDate(d.getDate() - i);
      const dateKey = toDateKey(d);
      const dayReminders = reminders.filter((r) => r.reminder_date === dateKey);
      if (dayReminders.length === 0) continue; // no history for this day
      const taken = dayReminders.filter((r) => r.status === "TAKEN").length;
      // Use frequency-based expected doses for adherence calculation.
      const expectedDay = expectedDailyDoses > 0 ? expectedDailyDoses : dayReminders.length;
      data.push({
        date: dateKey,
        label: MONTHS[d.getMonth()] + " " + d.getDate(),
        fullLabel:
          DAYS[d.getDay()] + ", " + MONTHS[d.getMonth()] + " " + d.getDate() + ", " + d.getFullYear(),
        taken,
        missed: dayReminders.filter((r) => r.status === "MISSED").length,
        total: expectedDay,
        adherence: Math.round((taken / expectedDay) * 100),
      });
    }
    return data; // already chronological (oldest -> newest)
  }, [reminders, expectedDailyDoses]);

  const trendDirection = useMemo(() => {
    if (adherenceTrend.length < 2) return { direction: "stable", diff: 0 };
    const diff =
      adherenceTrend[adherenceTrend.length - 1].adherence -
      adherenceTrend[0].adherence;
    if (diff > 5) return { direction: "up", diff };
    if (diff < -5) return { direction: "down", diff: Math.abs(diff) };
    return { direction: "stable", diff: 0 };
  }, [adherenceTrend]);

  const weeklyAvg = useMemo(() => {
    const valid = weeklyReport.filter((d) => d.taken > 0 || d.missed > 0);
    if (valid.length === 0) return 0;
    // Use frequency-based expected doses: expected = expectedDailyDoses * days with data
    const expectedTotal = expectedDailyDoses > 0 ? expectedDailyDoses * valid.length : valid.reduce((s, d) => s + d.taken + d.missed, 0);
    const taken = valid.reduce((s, d) => s + d.taken, 0);
    return expectedTotal > 0 ? Math.round((taken / expectedTotal) * 100) : 0;
  }, [weeklyReport, expectedDailyDoses]);

  // Soft, PillSync-consistent shades for Morning / Afternoon / Evening / Night.
  // Night is a real color (soft violet), NOT grey — a grey Night segment made
  // a single Night miss look like an empty/neutral donut.
  const PIE_COLORS_MISSED = {
    Morning: "#f87171",
    Afternoon: "#fb923c",
    Evening: "#fbbf24",
    Night: "#a78bfa",
  };

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="analytics-tooltip">
          <p className="analytics-tooltip-label">{label}</p>
          {payload.map((entry, idx) => (
            <p key={idx} className="analytics-tooltip-value" style={{ color: entry.color }}>
              {entry.name}: {entry.value}
            </p>
          ))}
        </div>
      );
    }
    return null;
  };

  const TrendTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const point = payload[0].payload;
      return (
        <div className="analytics-tooltip">
          <p className="analytics-tooltip-label">{point.fullLabel || label}</p>
          <p className="analytics-tooltip-value" style={{ color: "#0F766E" }}>
            Adherence: {point.adherence}%
          </p>
          <p className="analytics-tooltip-value" style={{ color: "#334155" }}>
            {point.taken} of {point.total} doses taken
          </p>
          {point.missed > 0 && (
            <p className="analytics-tooltip-value" style={{ color: "#dc2626" }}>
              {point.missed} missed
            </p>
          )}
        </div>
      );
    }
    return null;
  };

  const TrendIcon = trendDirection.direction === "up" ? FaArrowUp : trendDirection.direction === "down" ? FaArrowDown : FaMinus;

  return (
    <div className="analytics-section">
      <div className="analytics-header">
        <div className="analytics-header-left">
          <div className="analytics-header-icon"><FaChartBar /></div>
          <div>
            <h2 className="analytics-title">Dashboard Analytics</h2>
            <p className="analytics-subtitle">Detailed insights into your medication patterns</p>
          </div>
        </div>
        <div className="analytics-header-stats">
          <div className="analytics-header-stat">
            <span className="ahs-label">Weekly Avg</span>
            <span className="ahs-value" style={{ color: weeklyAvg >= 75 ? "#16a34a" : weeklyAvg >= 50 ? "#d97706" : "#dc2626" }}>
              {weeklyAvg}%
            </span>
          </div>
          <div className="analytics-header-divider" />
          <div className="analytics-header-stat">
            <span className="ahs-label">Trend</span>
            <span className={"ahs-value trend-" + trendDirection.direction}>
              <TrendIcon /> {trendDirection.diff}%
            </span>
          </div>
        </div>
      </div>

      <div className="analytics-grid-2">
        <div className="analytics-card">
          <div className="analytics-card-header">
            <div className="analytics-card-title-group">
              <FaChartBar className="analytics-card-icon" />
              <h3>Weekly Medication Report</h3>
            </div>
            <span className="analytics-card-badge">This Week</span>
          </div>
          <div className="analytics-chart-wrapper">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={weeklyReport} barGap={4} barCategoryGap={16}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="day" tick={{ fontSize: 12, fill: "#1e293b", fontWeight: 500 }} axisLine={{ stroke: "#e2e8f0" }} />
                <YAxis tick={{ fontSize: 12, fill: "#1e293b", fontWeight: 500 }} axisLine={{ stroke: "#e2e8f0" }} />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} iconType="circle" iconSize={8} />
                <Bar dataKey="taken" name="Taken" fill="#0F766E" radius={[6, 6, 0, 0]} animationDuration={1200} animationEasing="ease-out" />
                <Bar dataKey="missed" name="Missed" fill="#ef4444" radius={[6, 6, 0, 0]} animationDuration={1200} animationEasing="ease-out" />
                <Bar dataKey="pending" name="Pending" fill="#f59e0b" radius={[6, 6, 0, 0]} animationDuration={1200} animationEasing="ease-out" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="analytics-card">
          <div className="analytics-card-header">
            <div className="analytics-card-title-group">
              <FaChartLine className="analytics-card-icon" />
              <h3>Monthly Medication Report</h3>
            </div>
            <span className="analytics-card-badge">Last 6 Months</span>
          </div>
          <div className="analytics-chart-wrapper">
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={monthlyReport}>
                <CartesianGrid strokeDasharray="3 3" stroke="#353636" />
                <XAxis dataKey="month" tick={{ fontSize: 12, fill: "#1e293b", fontWeight: 500 }} axisLine={{ stroke: "#1f2022" }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 12, fill: "#1f2328" }} axisLine={{ stroke: "#e2e8f0" }} tickFormatter={(v) => v + "%"} />
                <Tooltip content={<CustomTooltip />} />
                <Line type="monotone" dataKey="adherence" name="Adherence %" stroke="#0F766E" strokeWidth={3} dot={{ fill: "#0F766E", strokeWidth: 2, r: 5 }} activeDot={{ r: 7, fill: "#0F766E", stroke: "#fff", strokeWidth: 2 }} animationDuration={1500} animationEasing="ease-out" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="analytics-grid-2">
        <div className="analytics-card">
          <div className="analytics-card-header">
            <div className="analytics-card-title-group">
              <FaChartPie className="analytics-card-icon" />
              <h3>Missed Dosage Analysis</h3>
            </div>
            <span className="analytics-card-badge">By Time Slot</span>
          </div>
          <div className="analytics-chart-wrapper">
            {hasMissedData ? (
              <div style={{ position: "relative", width: "100%" }}>
                <ResponsiveContainer width="100%" height={280}>
                  <PieChart>
                    <Pie data={missedPieData} cx="50%" cy="50%" innerRadius={60} outerRadius={100} paddingAngle={4} dataKey="value" animationDuration={1200} animationEasing="ease-out">
                      {missedPieData.map((entry) => (
                        <Cell key={entry.name} fill={PIE_COLORS_MISSED[entry.name]} />
                      ))}
                    </Pie>
                    <Tooltip content={<CustomTooltip />} />
                    <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} iconType="circle" iconSize={8} formatter={(value, entry) => value + " (" + entry.payload.value + ")"} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="analytics-donut-center">
                  <span className="analytics-donut-center-value">{totalMissed}</span>
                  <span className="analytics-donut-center-label">Missed</span>
                </div>
              </div>
            ) : (
              <div className="analytics-empty-chart">
                <FaChartPie style={{ fontSize: 48, color: "rgba(15, 118, 110, 0.45)", marginBottom: 12 }} />
                <p>No missed doses recorded yet.</p>
                <p style={{ fontSize: 13, color: "#94a3b8" }}>Keep up the good work! 🎉</p>
              </div>
            )}
          </div>
        </div>

        <div className="analytics-card">
          <div className="analytics-card-header">
            <div className="analytics-card-title-group">
              <FaChartLine className="analytics-card-icon" />
              <h3>Adherence Trend</h3>
            </div>
            <span className="analytics-card-badge">30-Day View</span>
          </div>
          {adherenceTrend.length === 0 ? (
            <div className="analytics-chart-wrapper">
              <div className="analytics-empty-chart">
                <FaChartLine style={{ fontSize: 48, color: "rgba(15, 118, 110, 0.45)", marginBottom: 12 }} />
                <p>No medication history available yet.</p>
                <p style={{ fontSize: 13, color: "#94a3b8" }}>Your adherence trend will appear here as you take your medications.</p>
              </div>
            </div>
          ) : (
            <>
              <div className="analytics-chart-wrapper">
                <ResponsiveContainer width="100%" height={280}>
                  <AreaChart data={adherenceTrend}>
                    <defs>
                      <linearGradient id="adherenceGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#0F766E" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#0F766E" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                    <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#1e293b", fontWeight: 500 }} axisLine={{ stroke: "#e2e8f0" }} interval="preserveStartEnd" />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 12, fill: "#1e293b", fontWeight: 500 }} axisLine={{ stroke: "#e2e8f0" }} tickFormatter={(v) => v + "%"} />
                    <Tooltip content={<TrendTooltip />} />
                    <Area type="monotone" dataKey="adherence" name="Adherence %" stroke="#0F766E" strokeWidth={3} fill="url(#adherenceGradient)" dot={{ fill: "#0F766E", strokeWidth: 2, r: 5 }} activeDot={{ r: 7, fill: "#0F766E", stroke: "#fff", strokeWidth: 2 }} animationDuration={1500} animationEasing="ease-out" connectNulls />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              {adherenceTrend.length === 1 && (
                <p className="analytics-trend-hint">More medication history is needed to show a trend.</p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default DashboardAnalytics;
