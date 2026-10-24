import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import "../styles/DashboardTopNav.css";

import {
  FaSearch,
  FaBell,
  FaCalendarAlt,
  FaPlus,
  FaPills,
  FaRobot,
  FaMoon,
  FaSun,
  FaUser,
  FaCog,
  FaQuestionCircle,
  FaSignOutAlt,
  FaBars,
  FaTimes,
  FaFileMedical,
  FaClock,
  FaExclamationTriangle,
  FaFlask,
  FaHome,
} from "react-icons/fa";

function DashboardTopNav({ userData = { username: "User", role: "Patient" }, medicines = [], reminders = [] }) {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState("");
  const [showNotifDropdown, setShowNotifDropdown] = useState(false);
  const [showQuickAddDropdown, setShowQuickAddDropdown] = useState(false);
  const [showProfileDropdown, setShowProfileDropdown] = useState(false);
  const [darkMode, setDarkMode] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [currentDateStr, setCurrentDateStr] = useState("");
  const notifRef = useRef(null);
  const quickAddRef = useRef(null);
  const profileRef = useRef(null);

  useEffect(() => {
    const now = new Date();
    setCurrentDateStr(now.toLocaleDateString("en-US", { month: "short", day: "numeric" }));
  }, []);

  useEffect(() => {
    if (darkMode) document.body.classList.add("dash-dark-mode");
    else document.body.classList.remove("dash-dark-mode");
  }, [darkMode]);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (notifRef.current && !notifRef.current.contains(e.target)) setShowNotifDropdown(false);
      if (quickAddRef.current && !quickAddRef.current.contains(e.target)) setShowQuickAddDropdown(false);
      if (profileRef.current && !profileRef.current.contains(e.target)) setShowProfileDropdown(false);
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);


  const pendingReminders = reminders.filter((r) => r.status === "PENDING" || r.status === "Pending");
  const missedReminders = reminders.filter((r) => r.status === "MISSED" || r.status === "Missed");
  const lowStockMeds = medicines.filter((m) => m.stock !== undefined && m.stock <= 5);
  const unreadCount = pendingReminders.length + missedReminders.length + lowStockMeds.length;

  const notificationItems = [
    ...(pendingReminders.length > 0 ? [{ icon: <FaClock />, label: `${pendingReminders.length} Upcoming Reminder(s)`, color: "#0F766E" }] : []),
    ...(missedReminders.length > 0 ? [{ icon: <FaExclamationTriangle />, label: `${missedReminders.length} Missed Medicine(s)`, color: "#dc2626" }] : []),
    ...(lowStockMeds.length > 0 ? [{ icon: <FaFlask />, label: `${lowStockMeds.length} Low Stock Medicine(s)`, color: "#d97706" }] : []),
  ];

  const handleSearch = (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    console.log("Searching:", searchQuery);
    setSearchQuery("");
  };

  const handleLogout = () => {
    localStorage.removeItem("access");
    localStorage.removeItem("refresh");
    navigate("/login");
  };

  const userInitial = (userData.username || "U")[0].toUpperCase();

  return (
    <>
      <nav className="dashboard-top-nav">
        {/* ── LEFT: Hamburger + Back to Home ── */}
        <div className="nav-left">
          <button className="hamburger-btn" onClick={() => setMobileMenuOpen(!mobileMenuOpen)} aria-label="Toggle menu">
            {mobileMenuOpen ? <FaTimes /> : <FaBars />}
          </button>

          {/* Back to Home — navigates to the landing page (route "/") */}
          <button
            className="nav-icon-btn nav-home-btn"
            onClick={() => navigate("/")}
            aria-label="Back to Home"
            title="Back to Home"
          >
            <FaHome />
          </button>
        </div>

        {/* ── CENTER: Wider Search Bar + Search Button ── */}
        <div className="nav-center">
          <div className="nav-search-bar-wrapper">
            <input
              type="text"
              className="nav-search-input"
              placeholder="Search medicines, reminders, reports..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleSearch(e); }}
            />
            <button className="nav-search-submit-btn" onClick={handleSearch} aria-label="Search">
              <FaSearch />
            </button>
          </div>
        </div>

        {/* ── RIGHT: Actions ── */}
        <div className="nav-right">
          {/* Notification Bell */}
          <div className="nav-action-item" ref={notifRef}>
            <button
              className="nav-icon-btn"
              onClick={() => { setShowNotifDropdown(!showNotifDropdown); setShowQuickAddDropdown(false); setShowProfileDropdown(false); }}
              aria-label="Notifications"
              title="Notifications"
            >
              <FaBell />
              {unreadCount > 0 && <span className="nav-badge">{unreadCount}</span>}
            </button>
            {showNotifDropdown && (
              <div className="nav-dropdown notif-dropdown">
                <div className="dropdown-header">
                  <span>Notifications</span>
                  <span className="dropdown-count">{unreadCount} new</span>
                </div>
                <div className="dropdown-body">
                  {notificationItems.length > 0 ? notificationItems.map((item, idx) => (
                    <div key={idx} className="notif-item">
                      <div className="notif-icon" style={{ color: item.color }}>{item.icon}</div>
                      <span className="notif-text">{item.label}</span>
                    </div>
                  )) : <div className="dropdown-empty">All clear! No notifications 🎉</div>}
                </div>
              </div>
            )}
          </div>

          {/* Calendar Date */}
          <div className="nav-action-item nav-date-display" title={currentDateStr}>
            <FaCalendarAlt className="nav-date-icon" />
            <span className="nav-date-text">{currentDateStr}</span>
          </div>

          {/* Quick Add (+) */}
          <div className="nav-action-item" ref={quickAddRef}>
            <button
              className="nav-icon-btn nav-quick-add-btn"
              onClick={() => { setShowQuickAddDropdown(!showQuickAddDropdown); setShowNotifDropdown(false); setShowProfileDropdown(false); }}
              aria-label="Quick add"
              title="Quick Add"
            >
              <FaPlus />
            </button>
            {showQuickAddDropdown && (
              <div className="nav-dropdown quickadd-dropdown">
                <div className="dropdown-header"><span>Quick Add</span></div>
                <div className="dropdown-body">
                  <div className="quickadd-item" onClick={() => { navigate("/medicines"); setShowQuickAddDropdown(false); }}>
                    <FaPills className="quickadd-icon" style={{ color: "#0F766E" }} /><span>Add Medicine</span>
                  </div>
                  <div className="quickadd-item" onClick={() => { navigate("/reminders"); setShowQuickAddDropdown(false); }}>
                    <FaClock className="quickadd-icon" style={{ color: "#2563eb" }} /><span>Add Reminder</span>
                  </div>
                  <div className="quickadd-item" onClick={() => { navigate("/medicines"); setShowQuickAddDropdown(false); }}>
                    <FaFileMedical className="quickadd-icon" style={{ color: "#d97706" }} /><span>Scan Prescription</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Ask AI */}
          <button className="nav-ai-btn" onClick={() => navigate("/aiassistant")} title="Ask AI">
            <FaRobot />
            <span>Ask AI</span>
          </button>

          {/* Dark Mode Toggle */}
          <button
            className="nav-icon-btn nav-dark-toggle"
            onClick={() => setDarkMode(!darkMode)}
            aria-label="Toggle dark mode"
            title={darkMode ? "Switch to Light Mode" : "Switch to Dark Mode"}
          >
            {darkMode ? <FaSun /> : <FaMoon />}
          </button>

          {/* Profile */}
          <div className="nav-action-item nav-profile" ref={profileRef}>
            <button
              className="nav-profile-btn"
              onClick={() => {
                setShowProfileDropdown(!showProfileDropdown);
                setShowNotifDropdown(false);
                setShowQuickAddDropdown(false);
              }}
              aria-label="User profile"
            >
              <div className="nav-avatar">{userInitial}</div>
              <div className="nav-profile-info">
                <span className="nav-profile-name">{userData.username || "User"}</span>
                <span className="nav-profile-role">{userData.role || "Patient"}</span>
              </div>
            </button>

            {showProfileDropdown && (
              <div className="nav-dropdown profile-dropdown">
                <div className="dropdown-profile-header">
                  <div className="dropdown-avatar">{userInitial}</div>
                  <div>
                    <span className="dropdown-name">{userData.username || "User"}</span>
                    <span className="dropdown-role">{userData.role || "Patient"}</span>
                  </div>
                </div>
                <div className="dropdown-body">
                  <div className="profile-menu-item" onClick={() => { navigate("/profile"); setShowProfileDropdown(false); }}>
                    <FaUser /><span>My Profile</span>
                  </div>
                  <div className="profile-menu-item" onClick={() => { navigate("/profile"); setShowProfileDropdown(false); }}>
                    <FaCog /><span>Settings</span>
                  </div>
                  <div className="profile-menu-item" onClick={() => setShowProfileDropdown(false)}>
                    <FaQuestionCircle /><span>Help</span>
                  </div>
                  <div className="dropdown-divider" />
                  <div className="profile-menu-item logout-item" onClick={handleLogout}>
                    <FaSignOutAlt /><span>Logout</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </nav>


      {/* ── MOBILE MENU ── */}
      {mobileMenuOpen && (
        <div className="mobile-overlay" onClick={() => setMobileMenuOpen(false)}>
          <div className="mobile-menu" onClick={(e) => e.stopPropagation()}>
            <div className="mobile-menu-header">
              <span className="nav-logo-icon">💊</span>
              <span className="nav-logo-text">PillSync</span>
              <button className="hamburger-btn" onClick={() => setMobileMenuOpen(false)}><FaTimes /></button>
            </div>
            <div className="mobile-menu-body">
              <div className="mobile-menu-item" onClick={() => { navigate("/dashboard"); setMobileMenuOpen(false); }}>Dashboard</div>
              <div className="mobile-menu-item" onClick={() => { navigate("/medicines"); setMobileMenuOpen(false); }}>Medicines</div>
              <div className="mobile-menu-item" onClick={() => { navigate("/reminders"); setMobileMenuOpen(false); }}>Reminders</div>
              <div className="mobile-menu-item" onClick={() => { navigate("/aiassistant"); setMobileMenuOpen(false); }}>AI Assistant</div>
              <div className="mobile-menu-item" onClick={() => { navigate("/profile"); setMobileMenuOpen(false); }}>Profile</div>
              <div className="mobile-menu-divider" />
              <div className="mobile-menu-item logout-item" onClick={handleLogout}>Logout</div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default DashboardTopNav;
