import {
  FaPills,
  FaBell,
  FaBullseye,
  FaHeartbeat,
  FaExclamationTriangle,
  FaRobot,
  FaCalendarAlt,
  FaQuoteLeft,
  FaPlusCircle,
  FaFileMedical,
  FaChartLine,
  FaArrowRight,
  FaLightbulb,
  FaBrain,
  FaHeart,
} from "react-icons/fa";

import { BsCapsule } from "react-icons/bs";

import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";

import Sidebar from "../components/Sidebar";
import DashboardTopNav from "../components/DashboardTopNav";
import StatCard from "../components/StatCard";
import ProgressChart from "../components/ProgressChart";
import HealthScore from "../components/HealthScore";
import RecentActivity from "../components/RecentActivity";
import ReminderCard from "../components/ReminderCard";
import api from "../services/api";
import usePushNotifications from "../hooks/usePushNotifications";
import AdherenceTracker from "../components/AdherenceTracker";
import DashboardAnalytics from "../components/DashboardAnalytics";
import "../styles/Dashboard.css";
import "../styles/EnhancedDashboard.css";


function Dashboard() {
  const [medicines, setMedicines] = useState([]);
  const [reminders, setReminders] = useState([]);
  const [notificationLogs, setNotificationLogs] = useState([]);
  const [userData, setUserData] = useState({ username: "User", role: "Patient" });
  const [loading, setLoading] = useState(true);
  // Set when the live reminders/medicines fetch fails, so the analytics
  // cards show a real error state instead of silently rendering fake 0s.
  const [fetchError, setFetchError] = useState(null);
  const navigate = useNavigate();

  // ── Enhanced Dashboard State ──
  const [greeting, setGreeting] = useState("Good Morning ☀️");
  const [currentDate, setCurrentDate] = useState("");
  const [healthQuote, setHealthQuote] = useState("");

  // Browser notifications: polls the backend's pending-push queue and shows
  // a browser Notification with live medicine/time data when a reminder fires.
  usePushNotifications();

  const HEALTH_QUOTES = [
    "The greatest wealth is health. — Virgil",
    "A healthy outside starts from the inside. — Robert Urich",
    "Take care of your body. It's the only place you have to live. — Jim Rohn",
    "Health is not about the weight you lose, it's about the life you gain.",
    "Your health is an investment, not an expense.",
    "Wellness is the complete integration of body, mind, and spirit.",
    "The greatest medicine of all is to teach people how not to need it. — Hippocrates",
    "The doctor of the future will give no medicine but will interest his patients in diet. — Thomas Edison",
  ];

  // Set greeting and date
  useEffect(() => {
    const now = new Date();
    const hour = now.getHours();
    if (hour < 12) setGreeting("Good Morning ☀️");
    else if (hour < 17) setGreeting("Good Afternoon 🌤️");
    else if (hour < 21) setGreeting("Good Evening 🌅");
    else setGreeting("Good Night 🌙");

    setCurrentDate(
      now.toLocaleDateString("en-US", {
        weekday: "long",
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    );
    setHealthQuote(
      HEALTH_QUOTES[Math.floor(Math.random() * HEALTH_QUOTES.length)]
    );
  }, []);

  // ── Live data fetch (medicines, reminders, activity logs, profile) ──
  const fetchData = useCallback(async () => {
    try {
      const [medRes, remRes, profileRes, logsRes] = await Promise.all([
        api.get("medicines/"),
        api.get("reminders/"),
        api.get("accounts/profile/").catch(() => null),
        api.get("reminders/notification-logs/").catch(() => ({ data: [] })),
      ]);
      setMedicines(medRes.data);
      setReminders(remRes.data);
      setNotificationLogs(Array.isArray(logsRes?.data) ? logsRes.data : []);
      if (profileRes?.data) {
        setUserData({
          username: profileRes.data.username || "User",
          role: profileRes.data.role || "Patient",
        });
      }
      setFetchError(null);
    } catch (error) {
      console.error("Failed to fetch dashboard data:", error);
      // NEVER substitute fake statistics for failed API calls — the
      // analytics cards render a real error state via the fetchError prop.
      setFetchError(
        "Couldn't load your data. Check your connection and try again."
      );
      const saved = JSON.parse(localStorage.getItem("medicines")) || [];
      setMedicines(saved);
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch on mount, then keep the dashboard live: re-fetch periodically and
  // whenever the tab regains focus, so reminder status changes (Taken /
  // Missed / Snoozed) made on any page appear instantly without a refresh.
  useEffect(() => {
    // Initial fetch is deferred one tick (matches the interval timing) so it
    // is not flagged as a synchronous setState within the effect body.
    const initial = setTimeout(fetchData, 0);
    const interval = setInterval(fetchData, 30000);
    const onFocus = () => fetchData();
    const onVisible = () => {
      if (!document.hidden) fetchData();
    };
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      clearTimeout(initial);
      clearInterval(interval);
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [fetchData]);

  const totalMedicines = medicines.length;

  const activeMedicines = medicines.filter(
    (item) => item.is_active === true
  ).length;

  const pendingMedicines = medicines.filter(
    (item) => item.is_active === false
  ).length;

  const nextMedicine =
    medicines.find((item) => item.frequency === "Morning") ||
    medicines.find((item) => item.frequency === "Afternoon") ||
    medicines.find((item) => item.frequency === "Night");


  const morningCount = medicines.filter(
    (item) => item.frequency === "Morning"
  ).length;

  const afternoonCount = medicines.filter(
    (item) => item.frequency === "Afternoon"
  ).length;

  const nightCount = medicines.filter(
    (item) => item.frequency === "Night"
  ).length;

  const pendingReminders = reminders.filter(
    (item) => item.status === "PENDING"
  ).length;

  const takenReminders = reminders.filter(
    (item) => item.status === "TAKEN"
  ).length;

  const adherenceScore = reminders.length > 0
    ? Math.round((takenReminders / reminders.length) * 100)
    : 0;

  // ── Health Score: REAL adherence over the user's confirmed doses. ──
  // TAKEN counts as taken, MISSED as not taken. TRIGGERED (fired but never
  // confirmed), PENDING and SNOOZED are not decided one way or the other,
  // so they are excluded — matching how the rest of the dashboard treats
  // them. All numbers come from the live reminders list fetched from the
  // backend — never hardcoded. Updates automatically with every poll /
  // focus refetch. ──
  const decidedReminders = reminders.filter(
    (r) => r.status === "TAKEN" || r.status === "MISSED"
  ).length;
  const healthScore =
    decidedReminders > 0
      ? Math.round((takenReminders / decidedReminders) * 100)
      : 0;
  // Until at least one dose is confirmed, there is no real score to show —
  // the card renders its "no data" state instead of a misleading 0/100.
  const hasHealthScoreData = decidedReminders > 0;

  // ── AI Health Insights ──
  const getHealthInsight = (score = 0) => {
    if (score >= 90)
      return {
        grade: "Excellent!",
        badge: "excellent",
        message:
          "You're doing fantastic! Your medication adherence is outstanding. Keep up this great habit - your consistency is building a strong foundation for your health. 🌟",
      };
    if (score >= 70)
      return {
        grade: "Good",
        badge: "good",
        message:
          "You're on the right track! Try to stay consistent with your medication schedule. Setting alarms or using our reminder system can help improve your adherence even more. 💪",
      };
    if (score >= 50)
      return {
        grade: "Fair",
        badge: "fair",
        message:
          "There's room for improvement, and that's okay! We recommend using the reminder system and setting up notifications to help you stay on track with your medications. You've got this! 💡",
      };
    return {
      grade: "Needs Attention",
      badge: "poor",
      message:
        "Your adherence is low. Please consult with your healthcare provider. Setting up regular reminders and organizing your medications can make a big difference. We're here to help! 🤝",
    };
  };
  const insight = getHealthInsight(adherenceScore);
  const healthGrade = getHealthInsight(healthScore).grade;


  return (
    <div className="dashboard-layout">

      {/* SIDEBAR FIXED */}
      <Sidebar />

      {/* MAIN AREA */}
      <div className="dashboard-content-wrapper">

        {/* PROFESSIONAL TOP NAVBAR */}
        <DashboardTopNav
          userData={userData}
          medicines={medicines}
          reminders={reminders}
        />

        {/* CONTENT */}
        <div className="dashboard-content">

          <div className="dashboard">

            {/* ── WELCOME SECTION ── */}
            <div className="welcome-section">
              <div className="welcome-left">
                <span className="welcome-greeting">{greeting}</span>
                <h1 className="welcome-title">
                  Welcome back, <span className="highlight-name">{userData.username || "User"}</span>
                </h1>
                <span className="welcome-date">
                  <FaCalendarAlt /> {currentDate}
                </span>
              </div>
              <div className="welcome-quote">
                <FaQuoteLeft className="quote-icon" />
                <span>{healthQuote}</span>
              </div>
            </div>

            <div className="cardGrid">

              <StatCard
                icon={<FaPills />}
                title="TOTAL MEDICINES"
                value={totalMedicines}
                subtitle={`${activeMedicines} Active | ${pendingMedicines} Pending`}
              />

              <StatCard
                icon={<FaBell />}
                title="NEXT REMINDER"
                value={nextMedicine ? nextMedicine.frequency : "No Reminder"}
                subtitle={`M:${morningCount} A:${afternoonCount} N:${nightCount}`}
              />

              <StatCard
                icon={<FaBullseye />}
                title="ADHERENCE SCORE"
                value={`${adherenceScore}%`}
                subtitle={`${takenReminders} of ${reminders.length} reminders taken`}
              />

              <StatCard
                icon={<FaHeartbeat />}
                title="ACTIVE MEDICINES"
                value={activeMedicines}
                subtitle={`Out of ${totalMedicines} Medicines`}
              />

              <StatCard
                icon={<FaExclamationTriangle />}
                title="UPCOMING REFILLS"
                value="2"
                subtitle="Within 7 days"
              />

              <StatCard
                icon={<BsCapsule />}
                title="AI HEALTH SCORE"
                value={healthScore}
                subtitle={healthGrade}
              />

            </div>

            <div className="chartSection">
              <ProgressChart
                reminders={reminders}
                medicines={medicines}
                loading={loading}
                error={fetchError}
              />
              <HealthScore
                score={healthScore}
                loading={loading}
                error={fetchError}
                empty={!hasHealthScoreData}
              />
            </div>

            <div className="bottomGrid">
              <RecentActivity
                reminders={reminders}
                medicines={medicines}
                notificationLogs={notificationLogs}
              />
              <ReminderCard reminders={reminders} medicines={medicines} />
            </div>


            {/* ════════════════════════════════════════════ */}
            {/*  ENHANCED DASHBOARD SECTIONS              */}
            {/* ════════════════════════════════════════════ */}

            {/* ── ROW 2: AI Insights + AI Assistant Quick Card (2 cols) ── */}
            <div className="enhanced-section enhanced-grid-2">

              {/* AI Health Insights */}
              <div className="enhanced-card ai-insights-card stagger-3">
                <div className="card-header">
                  <div className="card-header-left">
                    <div className="card-header-icon"><FaBrain /></div>
                    <h3>AI Health Insights</h3>
                  </div>
                  <span className={`ai-insight-badge ${insight.badge}`}>
                    <FaHeart /> {insight.grade}
                  </span>
                </div>
                <div className="ai-insight-content">
                  <div className="ai-insight-message">
                    <FaLightbulb style={{ color: "#d97706", marginRight: 8 }} />
                    {insight.message}
                  </div>
                  <div className="ai-insight-stats">
                    <div className="ai-insight-stat">
                      <span className="stat-number">{adherenceScore}%</span>
                      <span className="stat-label">Adherence</span>
                    </div>
                    <div className="ai-insight-stat">
                      <span className="stat-number">{takenReminders}</span>
                      <span className="stat-label">Taken</span>
                    </div>
                    <div className="ai-insight-stat">
                      <span className="stat-number">{pendingReminders}</span>
                      <span className="stat-label">Pending</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* AI Assistant Quick Card */}
              <div className="enhanced-card ai-assistant-quick-card stagger-4">
                <div className="card-header">
                  <div className="card-header-left">
                    <div className="card-header-icon"><FaRobot /></div>
                    <h3>AI Assistant</h3>
                  </div>
                  <span className="card-badge">Online</span>
                </div>
                <div className="ai-quick-content">
                  <p>
                    Need help with your medications? Ask our AI assistant about
                    medicine info, drug interactions, health tips, and more!
                  </p>
                  <button
                    className="open-ai-btn"
                    onClick={() => navigate("/aiassistant")}
                  >
                    <FaRobot /> Open AI Assistant <FaArrowRight />
                  </button>
                </div>
              </div>
            </div>

            {/* ── ROW 3: Quick Action Buttons (full width) ── */}
            <div className="enhanced-section">
              <div className="enhanced-card quick-actions-card stagger-5">
                <div className="card-header">
                  <div className="card-header-left">
                    <div className="card-header-icon"><FaPlusCircle /></div>
                    <h3>Quick Actions</h3>
                  </div>
                  <span className="card-badge" style={{ background: "#f1f5f9", color: "#475569" }}>
                    {medicines.length + reminders.length} total
                  </span>
                </div>
                <div className="quick-actions-grid">
                  <button className="quick-action-btn" onClick={() => navigate("/medicines")}>
                    <FaPills className="action-icon" />
                    <span className="action-label">Add Medicine</span>
                    <span className="action-sub">Add new medication</span>
                  </button>
                  <button className="quick-action-btn" onClick={() => navigate("/reminders")}>
                    <FaBell className="action-icon" />
                    <span className="action-label">Add Reminder</span>
                    <span className="action-sub">Set medication alarm</span>
                  </button>
                  <button className="quick-action-btn" onClick={() => navigate("/medicines")}>
                    <FaFileMedical className="action-icon" />
                    <span className="action-label">Scan Prescription</span>
                    <span className="action-sub">Upload & scan</span>
                  </button>
                  <button className="quick-action-btn" onClick={() => navigate("/reminders")}>
                    <FaChartLine className="action-icon" />
                    <span className="action-label">Generate Report</span>
                    <span className="action-sub">Export medication data</span>
                  </button>
                </div>
              </div>
            </div>

            {/* ════════════════════════════════════════════ */}
            {/*  FEATURE 1: MEDICATION ADHERENCE TRACKING  */}
            {/* ════════════════════════════════════════════ */}
            <AdherenceTracker
              reminders={reminders}
              medicines={medicines}
            />

            {/* ════════════════════════════════════════════ */}
            {/*  FEATURE 2: DASHBOARD ANALYTICS            */}
            {/* ════════════════════════════════════════════ */}
            <DashboardAnalytics
              reminders={reminders}
              medicines={medicines}
            />

          </div>

        </div>

      </div>

    </div>
  );
}


export default Dashboard;