import { useMemo, useCallback } from "react";
import { FaCheckCircle, FaTimesCircle, FaClock, FaSun, FaMoon, FaCloudSun, FaChartLine } from "react-icons/fa";
import { BsCapsule } from "react-icons/bs";
import AnimatedCounter from "./AnimatedCounter";
import CircularProgress from "./CircularProgress";
import "../styles/AdherenceTracker.css";

function AdherenceTracker({ reminders = [], medicines = [] }) {
  const today = new Date().toISOString().split("T")[0];

  const todayReminders = useMemo(
    () => reminders.filter((r) => r.reminder_date === today),
    [reminders, today]
  );

  const takenToday = useMemo(
    () => todayReminders.filter((r) => r.status === "TAKEN").length,
    [todayReminders]
  );

  const missedToday = useMemo(
    () => todayReminders.filter((r) => r.status === "MISSED").length,
    [todayReminders]
  );

  const pendingToday = useMemo(
    () => todayReminders.filter((r) => r.status === "PENDING").length,
    [todayReminders]
  );

  // Compute expected daily doses from active medicines' frequency_doses_per_day.
  // Adherence = taken / expected, where expected comes from each medicine's
  // frequency setting (1–4 times/day) rather than a hard-coded constant.
  const activeMedicines = useMemo(
    () => medicines.filter((m) => m.is_active !== false),
    [medicines]
  );
  const expectedDailyDoses = useMemo(
    () => activeMedicines.reduce((sum, m) => sum + (m.frequency_doses_per_day || 1), 0),
    [activeMedicines]
  );

  const totalReminders = reminders.length;
  const totalTaken = reminders.filter((r) => r.status === "TAKEN").length;
  // Use the actual expected daily doses from the medicine frequency field.
  // For today: adherence = taken today / expected daily doses from all active medicines.
  // Fallback to reminder count when no medicines or expected doses are available.
  const adherencePercent = expectedDailyDoses > 0
    ? Math.round((takenToday / expectedDailyDoses) * 100)
    : (totalReminders > 0 ? Math.round((totalTaken / totalReminders) * 100) : 0);

  const getTimeSlot = (timeStr) => {
    if (!timeStr) return "other";
    const [h] = timeStr.split(":").map(Number);
    if (h >= 5 && h < 12) return "morning";
    if (h >= 12 && h < 17) return "afternoon";
    if (h >= 17 && h < 21) return "evening";
    return "night";
  };

  const getMedicineName = useCallback(
    (medicineId) => {
      const med = medicines.find((m) => m.id === medicineId);
      return med ? med.medicine_name : "Medicine #" + medicineId;
    },
    [medicines]
  );

  const timeSlots = [
    { key: "morning", label: "Morning", icon: <FaSun />, time: "5:00 AM - 12:00 PM", color: "#0d9488", bgColor: "#f0fdfa" },
    { key: "afternoon", label: "Afternoon", icon: <FaCloudSun />, time: "12:00 PM - 5:00 PM", color: "#0f766e", bgColor: "#ccfbf1" },
    { key: "evening", label: "Evening", icon: <FaClock />, time: "5:00 PM - 9:00 PM", color: "#14b8a6", bgColor: "#99f6e4" },
    { key: "night", label: "Night", icon: <FaMoon />, time: "9:00 PM - 5:00 AM", color: "#115e59", bgColor: "#5eead4" },
  ];

  const getSlotReminders = (slotKey) => {
    return todayReminders.filter((r) => getTimeSlot(r.reminder_time) === slotKey);
  };

  const getAdherenceStatus = (pct) => {
    if (pct >= 80) return { label: "Good", color: "#0F766E", bgColor: "#ccfbf1", icon: "\u{1F44D}" };
    // "Average" badge uses the project green (teal) instead of amber — the
    // circle/bar below carry the red/green adherence rule.
    if (pct >= 50) return { label: "Average", color: "#0F766E", bgColor: "#ccfbf1", icon: "\u{1F4CA}" };
    return { label: "Needs Improvement", color: "#dc2626", bgColor: "#fee2e2", icon: "\u26A0\uFE0F" };
  };

  const adherenceStatus = getAdherenceStatus(adherencePercent);

  return (
    <div className="adherence-section">
      <div className="adherence-header">
        <div className="adherence-header-left">
          <div className="adherence-header-icon">
            <FaChartLine />
          </div>
          <div>
            <h2 className="adherence-title">Medication Adherence Tracking</h2>
            <p className="adherence-subtitle">Monitor your daily medication compliance</p>
          </div>
        </div>
        <div className="adherence-header-badge">
          <span className="adherence-badge-dot" style={{ background: adherenceStatus.color }} />
          {adherenceStatus.icon} {adherenceStatus.label}
        </div>
      </div>

      <div className="adherence-summary-grid">
        <div className="adherence-summary-card taken-card">
          <div className="adherence-summary-icon"><FaCheckCircle /></div>
          <div className="adherence-summary-info">
            <span className="adherence-summary-label">Medicines Taken Today</span>
            <span className="adherence-summary-value">
              <AnimatedCounter value={takenToday} duration={1200} />
            </span>
            <span className="adherence-summary-sub">
              {takenToday > 0 ? "All doses completed \u2713" : "No doses taken yet"}
            </span>
          </div>
          <div className="adherence-summary-trend up">
            <span className="trend-arrow">&uarr;</span>
            <span className="trend-text">{totalTaken} total</span>
          </div>
        </div>

        <div className="adherence-summary-card missed-card">
          <div className="adherence-summary-icon"><FaTimesCircle /></div>
          <div className="adherence-summary-info">
            <span className="adherence-summary-label">Missed Doses</span>
            <span className="adherence-summary-value">
              <AnimatedCounter value={missedToday} duration={1200} />
            </span>
            <span className="adherence-summary-sub">
              {missedToday > 0 ? missedToday + " dose" + (missedToday > 1 ? "s" : "") + " missed today" : "No missed doses! 🎉"}
            </span>
          </div>
          <div className="adherence-summary-trend down">
            <span className="trend-arrow">&darr;</span>
            <span className="trend-text">{pendingToday} pending</span>
          </div>
        </div>

        <div className="adherence-summary-card pending-card">
          <div className="adherence-summary-icon"><FaClock /></div>
          <div className="adherence-summary-info">
            <span className="adherence-summary-label">Pending Reminders</span>
            <span className="adherence-summary-value">
              <AnimatedCounter value={pendingToday} duration={1200} />
            </span>
            <span className="adherence-summary-sub">
              {pendingToday > 0 ? "Still to take today" : "All reminders completed! 🎉"}
            </span>
          </div>
          <div className="adherence-summary-trend neutral">
            <span className="trend-arrow">&rarr;</span>
            <span className="trend-text">{todayReminders.length} total today</span>
          </div>
        </div>

        <div className="adherence-summary-card total-card">
          <div className="adherence-summary-icon"><BsCapsule /></div>
          <div className="adherence-summary-info">
            <span className="adherence-summary-label">Active Medications</span>
            <span className="adherence-summary-value">
              <AnimatedCounter value={medicines.filter((m) => m.is_active !== false).length} duration={1200} />
            </span>
            <span className="adherence-summary-sub">{medicines.length} total registered</span>
          </div>
          <div className="adherence-summary-trend neutral">
            <span className="trend-arrow">&sum;</span>
            <span className="trend-text">{todayReminders.length} today</span>
          </div>
        </div>
      </div>

      <div className="adherence-main-grid">
        <div className="adherence-card daily-history-card">
          <div className="adherence-card-header">
            <div className="adherence-card-title-group">
              <FaClock className="adherence-card-icon" />
              <h3>Daily Medication History</h3>
            </div>
            <span className="adherence-card-badge">
              {todayReminders.length} reminder{todayReminders.length !== 1 ? "s" : ""}
            </span>
          </div>

          <div className="daily-timeline">
            {timeSlots.map((slot) => {
              const slotReminders = getSlotReminders(slot.key);
              return (
                <div key={slot.key} className="timeline-slot">
                  <div className="timeline-slot-header">
                    <div className="timeline-slot-icon" style={{ background: slot.bgColor, color: slot.color }}>
                      {slot.icon}
                    </div>
                    <div className="timeline-slot-info">
                      <span className="timeline-slot-label">{slot.label}</span>
                      <span className="timeline-slot-time">{slot.time}</span>
                    </div>
                    <span className="timeline-slot-count">{slotReminders.length}</span>
                  </div>

                  {slotReminders.length > 0 ? (
                    <div className="timeline-items">
                      {slotReminders.map((r, idx) => {
                        const statusIcon =
                          r.status === "TAKEN" ? <FaCheckCircle className="status-taken" />
                            : r.status === "MISSED" ? <FaTimesCircle className="status-missed" />
                            : <FaClock className="status-pending" />;
                        const statusText =
                          r.status === "TAKEN" ? "Taken"
                            : r.status === "MISSED" ? "Missed"
                            : "Pending";
                        return (
                          <div key={idx} className={"timeline-item status-" + r.status.toLowerCase()}>
                            <div className="timeline-item-dot" />
                            <div className="timeline-item-content">
                              <span className="timeline-item-name">{getMedicineName(r.medicine)}</span>
                              <span className="timeline-item-time">
                                {r.reminder_time
                                  ? new Date("2000-01-01T" + r.reminder_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
                                  : "--:--"}
                              </span>
                            </div>
                            <span className={"timeline-item-status " + r.status.toLowerCase()}>
                              {statusIcon} {statusText}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="timeline-empty">
                      <span>No medications scheduled for this time slot</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        <div className="adherence-card adherence-percentage-card">
          <div className="adherence-card-header">
            <div className="adherence-card-title-group">
              <FaChartLine className="adherence-card-icon" />
              <h3>Adherence Percentage</h3>
            </div>
            <span className="adherence-card-badge" style={{ background: adherenceStatus.bgColor, color: adherenceStatus.color }}>
              {adherenceStatus.icon} {adherenceStatus.label}
            </span>
          </div>

          <div className="adherence-percentage-body">
            <div className="adherence-circle-section">
              <CircularProgress
                percentage={adherencePercent}
                size={132}
                strokeWidth={10}
                color={adherencePercent >= 80 ? "#0F766E" : "#f87171"}
                label="Overall"
              />
              <div className="adherence-circle-stats">
                <div className="adherence-stat-item">
                  <span className="adherence-stat-value" style={{ color: "#0F766E" }}>{totalTaken}</span>
                  <span className="adherence-stat-label">Taken</span>
                </div>
                <div className="adherence-stat-divider" />
                <div className="adherence-stat-item">
                  <span className="adherence-stat-value" style={{ color: "#0F766E" }}>{reminders.filter((r) => r.status === "MISSED").length}</span>
                  <span className="adherence-stat-label">Missed</span>
                </div>
                <div className="adherence-stat-divider" />
                <div className="adherence-stat-item">
                  <span className="adherence-stat-value" style={{ color: "#0F766E" }}>{reminders.filter((r) => r.status === "PENDING").length}</span>
                  <span className="adherence-stat-label">Pending</span>
                </div>
                <div className="adherence-stat-divider" />
                <div className="adherence-stat-item">
                  <span className="adherence-stat-value" style={{ color: "#0F766E" }}>{totalReminders}</span>
                  <span className="adherence-stat-label">Total</span>
                </div>
              </div>
            </div>

            <div className="adherence-bar-section">
              <div className="adherence-bar-header">
                <span className="adherence-bar-label">Adherence Rate</span>
                <span className="adherence-bar-percent" style={{ color: adherencePercent >= 80 ? "#0F766E" : "#f87171" }}>{adherencePercent}%</span>
              </div>
              <div className="adherence-bar-track">
                <div
                  className="adherence-bar-fill"
                  style={{
                    width: adherencePercent + "%",
                    // 0-79% soft light red · 80-100% exact project green.
                    background: adherencePercent >= 80
                      ? "linear-gradient(90deg, #0d9488, #14b8a6)"
                      : "linear-gradient(90deg, #f87171, #fca5a5)"
                  }}
                />
              </div>
              <div className="adherence-bar-markers">
                <span>0%</span><span>25%</span><span>50%</span><span>75%</span><span>100%</span>
              </div>
            </div>

            <div className="adherence-breakdown">
              <div className="adherence-breakdown-item">
                <div className="breakdown-header">
                  <span className="breakdown-label"><FaCheckCircle style={{ color: "#0F766E", fontSize: 14 }} /> Taken</span>
                  <span className="breakdown-value">{totalTaken}</span>
                </div>
                <div className="breakdown-bar">
                  <div className="breakdown-fill taken-fill" style={{ width: (totalReminders > 0 ? (totalTaken / totalReminders) * 100 : 0) + "%" }} />
                </div>
              </div>
              <div className="adherence-breakdown-item">
                <div className="breakdown-header">
                  <span className="breakdown-label"><FaTimesCircle style={{ color: "#0F766E", fontSize: 14 }} /> Missed</span>
                  <span className="breakdown-value">{reminders.filter((r) => r.status === "MISSED").length}</span>
                </div>
                <div className="breakdown-bar">
                  <div className="breakdown-fill missed-fill" style={{ width: (totalReminders > 0 ? (reminders.filter((r) => r.status === "MISSED").length / totalReminders) * 100 : 0) + "%" }} />
                </div>
              </div>
              <div className="adherence-breakdown-item">
                <div className="breakdown-header">
                  <span className="breakdown-label"><FaClock style={{ color: "#0F766E", fontSize: 14 }} /> Pending</span>
                  <span className="breakdown-value">{reminders.filter((r) => r.status === "PENDING").length}</span>
                </div>
                <div className="breakdown-bar">
                  <div className="breakdown-fill pending-fill" style={{ width: (totalReminders > 0 ? (reminders.filter((r) => r.status === "PENDING").length / totalReminders) * 100 : 0) + "%" }} />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default AdherenceTracker;
