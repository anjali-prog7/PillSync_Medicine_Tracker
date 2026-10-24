import { useState, useEffect, useCallback } from "react";
import {
  FaHistory,
  FaSpinner,
  FaCheckCircle,
  FaTimesCircle,
  FaBell,
  FaFilter,
  FaDownload,
} from "react-icons/fa";

import Navbar from "../components/Navbar";
import Sidebar from "../components/Sidebar";
import DashboardTopNav from "../components/DashboardTopNav";
import api from "../services/api";
import "../styles/Reminder.css";

function History() {
  const [loading, setLoading] = useState(true);
  const [reminders, setReminders] = useState([]);
  const [notificationLogs, setNotificationLogs] = useState([]);
  const [userData, setUserData] = useState({ username: "User", role: "Patient" });
  const [filter, setFilter] = useState("ALL");

  const fetchData = useCallback(async () => {
    try {
      const [remRes, logsRes, profileRes] = await Promise.all([
        api.get("reminders/"),
        api.get("reminders/notification-logs/").catch(() => ({ data: [] })),
        api.get("accounts/profile/").catch(() => null),
      ]);
      setReminders(remRes.data);
      setNotificationLogs(Array.isArray(logsRes?.data) ? logsRes.data : []);
      if (profileRes?.data) {
        setUserData({
          username: profileRes.data.username || "User",
          role: profileRes.data.role || "Patient",
        });
      }
    } catch (error) {
      console.error("Failed to fetch history:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const filteredReminders =
    filter === "ALL"
      ? reminders
      : reminders.filter((r) => r.status === filter);

  const exportCSV = () => {
    const rows = [["Medicine ID", "Time", "Date", "Status"]];
    filteredReminders.forEach((item) => {
      rows.push([
        item.medicine,
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

  if (loading) {
    return (
      <>
        <Navbar />
        <div className="loading-overlay">
          <div className="loading-spinner">
            <FaSpinner className="spinner-icon" />
            <p>Loading history...</p>
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
          medicines={[]}
          reminders={reminders}
        />

        <div className="dashboard-content">
          <div className="reminder-page history-page">
            {/* Header */}
            <div className="reminder-header">
              <div>
                <h1>
                  <FaHistory /> Medication History
                </h1>
                <p>View your complete medication and reminder history</p>
              </div>
              <button className="export-btn" onClick={exportCSV}>
                <FaDownload /> Export CSV
              </button>
            </div>

            {/* Filter */}
            <div style={{ marginBottom: 24, display: "flex", gap: 12, alignItems: "center" }}>
              <FaFilter style={{ color: "#0D766E" }} />
              {["ALL", "TAKEN", "MISSED", "TRIGGERED", "PENDING", "SNOOZED"].map(
                (f) => (
                  <button
                    key={f}
                    onClick={() => setFilter(f)}
                    style={{
                      padding: "8px 16px",
                      borderRadius: 20,
                      border: filter === f ? "2px solid #0D766E" : "2px solid #e5e7eb",
                      background: filter === f ? "#0D766E" : "#fff",
                      color: filter === f ? "#fff" : "#475569",
                      cursor: "pointer",
                      fontWeight: 600,
                      fontSize: 13,
                      transition: "0.2s",
                    }}
                  >
                    {f}
                  </button>
                )
              )}
            </div>

            {/* Reminder History Table */}
            <div className="history" style={{ marginBottom: 40 }}>
              <div className="history-top">
                <h2>Reminder History ({filteredReminders.length})</h2>
              </div>
              {filteredReminders.length === 0 ? (
                <div className="empty">
                  <h2>No History Found</h2>
                  <p>No reminders match the selected filter.</p>
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
                    {filteredReminders.map((item) => (
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

            {/* Notification Logs */}
            <div className="history" style={{ marginBottom: 40 }}>
              <div className="history-top">
                <h2>
                  <FaBell /> Notification Logs ({notificationLogs.length})
                </h2>
              </div>
              {notificationLogs.length === 0 ? (
                <div className="empty">
                  <h2>No Notifications Yet</h2>
                  <p>Notification logs will appear here.</p>
                </div>
              ) : (
                <table>
                  <thead>
                    <tr>
                      <th>Title</th>
                      <th>Channel</th>
                      <th>Status</th>
                      <th>Created At</th>
                    </tr>
                  </thead>
                  <tbody>
                    {notificationLogs.map((log) => (
                      <tr key={log.id}>
                        <td>{log.title || "Medicine Reminder"}</td>
                        <td>{log.channel || "PUSH"}</td>
                        <td>
                          <span
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 6,
                              padding: "4px 12px",
                              borderRadius: 20,
                              fontSize: 13,
                              fontWeight: 600,
                              background:
                                log.status === "SENT" ? "#dcfce7" : "#fee2e2",
                              color:
                                log.status === "SENT" ? "#166534" : "#991b1b",
                            }}
                          >
                            {log.status === "SENT" ? (
                              <FaCheckCircle />
                            ) : (
                              <FaTimesCircle />
                            )}
                            {log.status}
                          </span>
                        </td>
                        <td>
                          {log.created_at
                            ? new Date(log.created_at).toLocaleString()
                            : "—"}
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

export default History;
