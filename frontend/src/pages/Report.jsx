import { useState, useEffect, useCallback } from "react";
import {
  FaFileMedical,
  FaChartBar,
  FaDownload,
  FaSpinner,
  FaPills,
  FaCheckCircle,
  FaTimesCircle,
  FaClock,
} from "react-icons/fa";

import Navbar from "../components/Navbar";
import Sidebar from "../components/Sidebar";
import DashboardTopNav from "../components/DashboardTopNav";
import api from "../services/api";
import "../styles/Reminder.css";

function Report() {
  const [loading, setLoading] = useState(true);
  const [medicines, setMedicines] = useState([]);
  const [reminders, setReminders] = useState([]);
  const [userData, setUserData] = useState({ username: "User", role: "Patient" });
  const [dateRange, setDateRange] = useState("all");

  const fetchData = useCallback(async () => {
    try {
      const [medRes, remRes, profileRes] = await Promise.all([
        api.get("medicines/"),
        api.get("reminders/"),
        api.get("accounts/profile/").catch(() => null),
      ]);
      setMedicines(medRes.data);
      setReminders(remRes.data);
      if (profileRes?.data) {
        setUserData({
          username: profileRes.data.username || "User",
          role: profileRes.data.role || "Patient",
        });
      }
    } catch (error) {
      console.error("Failed to fetch report data:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Compute report stats
  const totalReminders = reminders.length;
  const takenReminders = reminders.filter((r) => r.status === "TAKEN").length;
  const missedReminders = reminders.filter((r) => r.status === "MISSED").length;
  const pendingReminders = reminders.filter((r) => r.status === "PENDING").length;
  const triggeredReminders = reminders.filter((r) => r.status === "TRIGGERED").length;
  const snoozedReminders = reminders.filter((r) => r.status === "SNOOZED").length;

  const decidedReminders = takenReminders + missedReminders;
  const adherenceRate =
    decidedReminders > 0 ? Math.round((takenReminders / decidedReminders) * 100) : 0;

  // Filter by date range
  const getFilteredReminders = () => {
    if (dateRange === "all") return reminders;
    const now = new Date();
    const cutoff = new Date();
    if (dateRange === "week") cutoff.setDate(now.getDate() - 7);
    else if (dateRange === "month") cutoff.setMonth(now.getMonth() - 1);
    else if (dateRange === "3months") cutoff.setMonth(now.getMonth() - 3);

    return reminders.filter((r) => {
      if (!r.reminder_date) return false;
      const d = new Date(r.reminder_date);
      return d >= cutoff;
    });
  };

  const filtered = getFilteredReminders();

  // Per-medicine breakdown
  const medicineBreakdown = medicines.map((med) => {
    const medReminders = filtered.filter((r) => r.medicine === med.id);
    const taken = medReminders.filter((r) => r.status === "TAKEN").length;
    const missed = medReminders.filter((r) => r.status === "MISSED").length;
    const total = medReminders.length;
    const decided = taken + missed;
    const rate = decided > 0 ? Math.round((taken / decided) * 100) : null;
    return { ...med, total, taken, missed, rate };
  });

  const exportReport = () => {
    const rows = [
      ["Medicine", "Total Reminders", "Taken", "Missed", "Adherence Rate"],
    ];
    medicineBreakdown.forEach((med) => {
      rows.push([
        med.medicine_name,
        med.total,
        med.taken,
        med.missed,
        med.rate !== null ? `${med.rate}%` : "N/A",
      ]);
    });
    rows.push([]);
    rows.push(["Overall Adherence", `${adherenceRate}%`]);
    rows.push(["Total Reminders", totalReminders]);
    rows.push(["Taken", takenReminders]);
    rows.push(["Missed", missedReminders]);

    const csv = rows.map((e) => e.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `MedicationReport_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
  };

  if (loading) {
    return (
      <>
        <Navbar />
        <div className="loading-overlay">
          <div className="loading-spinner">
            <FaSpinner className="spinner-icon" />
            <p>Generating report...</p>
          </div>
        </div>
      </>
    );
  }

  return (
    <div className="dashboard-layout">
      <Sidebar />

      <div className="dashboard-content-wrapper">
        <DashboardTopNav
          userData={userData}
          medicines={medicines}
          reminders={reminders}
        />

        <div className="dashboard-content">
          <div className="reminder-page report-page">
            {/* Header */}
            <div className="reminder-header">
              <div>
                <h1>
                  <FaFileMedical /> Medication Report
                </h1>
                <p>Comprehensive medication adherence and usage report</p>
              </div>
              <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                <select
                  value={dateRange}
                  onChange={(e) => setDateRange(e.target.value)}
                  style={{
                    padding: "10px 14px",
                    borderRadius: 10,
                    border: "2px solid #0D766E",
                    color: "#0D766E",
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  <option value="all">All Time</option>
                  <option value="week">Last 7 Days</option>
                  <option value="month">Last 30 Days</option>
                  <option value="3months">Last 3 Months</option>
                </select>
                <button className="export-btn" onClick={exportReport}>
                  <FaDownload /> Export Report
                </button>
              </div>
            </div>

            {/* Summary Stats */}
            <div className="summary-grid" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
              <div className="summary-card" style={{ borderLeft: "5px solid #0D766E" }}>
                <h3>Adherence Rate</h3>
                <h1 style={{ color: adherenceRate >= 70 ? "#0D766E" : "#dc2626" }}>
                  {adherenceRate}%
                </h1>
              </div>
              <div className="summary-card" style={{ borderLeft: "5px solid #16a34a" }}>
                <h3>Taken</h3>
                <h1 style={{ color: "#16a34a" }}>{takenReminders}</h1>
              </div>
              <div className="summary-card" style={{ borderLeft: "5px solid #dc2626" }}>
                <h3>Missed</h3>
                <h1 style={{ color: "#dc2626" }}>{missedReminders}</h1>
              </div>
              <div className="summary-card" style={{ borderLeft: "5px solid #f59e0b" }}>
                <h3>Pending</h3>
                <h1 style={{ color: "#f59e0b" }}>{pendingReminders}</h1>
              </div>
            </div>

            {/* Adherence Progress Bar */}
            <div className="adherence-card">
              <div className="adherence-top">
                <h2>Overall Adherence</h2>
                <h1>{adherenceRate}%</h1>
              </div>
              <div className="progress-bar">
                <div
                  className="progress-fill"
                  style={{ width: `${adherenceRate}%` }}
                ></div>
              </div>
              <p>
                {takenReminders} of {decidedReminders} decided doses taken
                {triggeredReminders > 0 && ` • ${triggeredReminders} triggered`}
                {snoozedReminders > 0 && ` • ${snoozedReminders} snoozed`}
              </p>
            </div>

            {/* Per-Medicine Breakdown */}
            <div className="history" style={{ marginTop: 30 }}>
              <h2>
                <FaPills /> Per-Medicine Breakdown
              </h2>
              {medicineBreakdown.length === 0 ? (
                <div className="empty">
                  <h2>No Medicines Added</h2>
                  <p>Add medicines to see per-medicine report data.</p>
                </div>
              ) : (
                <table>
                  <thead>
                    <tr>
                      <th>Medicine</th>
                      <th>Total</th>
                      <th>
                        <FaCheckCircle style={{ marginRight: 4 }} /> Taken
                      </th>
                      <th>
                        <FaTimesCircle style={{ marginRight: 4 }} /> Missed
                      </th>
                      <th>
                        <FaClock style={{ marginRight: 4 }} /> Pending
                      </th>
                      <th>Adherence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {medicineBreakdown.map((med) => (
                      <tr key={med.id}>
                        <td style={{ fontWeight: 600 }}>{med.medicine_name}</td>
                        <td>{med.total}</td>
                        <td style={{ color: "#16a34a", fontWeight: 600 }}>
                          {med.taken}
                        </td>
                        <td style={{ color: "#dc2626", fontWeight: 600 }}>
                          {med.missed}
                        </td>
                        <td>{med.total - med.taken - med.missed}</td>
                        <td>
                          {med.rate !== null ? (
                            <span
                              style={{
                                padding: "4px 12px",
                                borderRadius: 20,
                                fontSize: 13,
                                fontWeight: 600,
                                background:
                                  med.rate >= 70 ? "#dcfce7" : med.rate >= 50 ? "#fef3c7" : "#fee2e2",
                                color:
                                  med.rate >= 70 ? "#166534" : med.rate >= 50 ? "#92400e" : "#991b1b",
                              }}
                            >
                              {med.rate}%
                            </span>
                          ) : (
                            <span style={{ color: "#94a3b8" }}>N/A</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            {/* Detailed Reminder Log */}
            <div className="history" style={{ marginTop: 30 }}>
              <div className="history-top">
                <h2>
                  <FaChartBar /> Detailed Reminder Log ({filtered.length})
                </h2>
              </div>
              {filtered.length === 0 ? (
                <div className="empty">
                  <h2>No Data</h2>
                  <p>No reminders found for the selected period.</p>
                </div>
              ) : (
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
                    {filtered.map((item) => (
                      <tr key={item.id}>
                        <td>{item.medicine}</td>
                        <td>{(item.reminder_time || "").substring(0, 5)}</td>
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
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Report;
