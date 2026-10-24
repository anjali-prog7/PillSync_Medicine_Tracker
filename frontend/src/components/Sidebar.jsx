import { useState } from "react";
import "../styles/Sidebar.css";
import { useNavigate, useLocation } from "react-router-dom";

import {
  FaThLarge,
  FaChartBar,
  FaFileMedical,
  FaHistory,
  FaCog,
  FaSignOutAlt,
  FaPills,
  FaChevronLeft,
  FaChevronRight,
} from "react-icons/fa";

import { HiDocumentReport } from "react-icons/hi";

function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  const handleLogout = () => {
    localStorage.removeItem("access");
    localStorage.removeItem("refresh");
    navigate("/login");
  };

  const menuItems = [
    { icon: <FaThLarge />, label: "Dashboard", path: "/dashboard" },
    { icon: <FaPills />, label: "Refill", path: "/refill" },
    { icon: <FaChartBar />, label: "Analytics", path: "/dashboard" },
    { icon: <FaFileMedical />, label: "Prescription OCR", path: "/dashboard/prescription-ocr" },
    { icon: <HiDocumentReport />, label: "Report", path: "/report" },
    { icon: <FaHistory />, label: "History", path: "/history" },
    { icon: <FaCog />, label: "Settings", path: "/profile" },
  ];

  return (
    <div className={`sidebar ${collapsed ? "collapsed" : ""}`}>
      {/* Sidebar Header */}
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <span className="sidebar-logo-icon">💊</span>
          {!collapsed && (
            <div className="sidebar-logo-text-wrapper">
              <span className="sidebar-logo-text">PillSync</span>
              <span className="sidebar-logo-sub">Medicine Reminder</span>
            </div>
          )}
        </div>
        <button
          className="sidebar-collapse-btn"
          onClick={() => setCollapsed(!collapsed)}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <FaChevronRight /> : <FaChevronLeft />}
        </button>
      </div>

      {/* Navigation Menu */}
      <ul className="sidebar-menu">
        {menuItems.map((item) => (
          <li
            key={item.label}
            className={
              location.pathname === item.path
                ? "sidebar-menu-item active"
                : "sidebar-menu-item"
            }
            onClick={() => navigate(item.path)}
            title={collapsed ? item.label : undefined}
          >
            <span className="sidebar-menu-icon">{item.icon}</span>
            {!collapsed && <span className="sidebar-menu-label">{item.label}</span>}
          </li>
        ))}
      </ul>

      {/* Logout */}
      <div
        className="sidebar-logout"
        onClick={handleLogout}
        title={collapsed ? "Logout" : undefined}
      >
        <span className="sidebar-menu-icon">
          <FaSignOutAlt />
        </span>
        {!collapsed && <span className="sidebar-menu-label">Logout</span>}
      </div>
    </div>
  );
}

export default Sidebar;
