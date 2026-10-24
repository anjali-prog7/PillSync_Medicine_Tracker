import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";

import Sidebar from "../components/Sidebar";
import DashboardTopNav from "../components/DashboardTopNav";
import api from "../services/api";
import "../styles/Profile.css";

import {
  FaPills,
  FaBell,
  FaCalendarCheck,
  FaCheckCircle,
  FaUser,
  FaEnvelope,
  FaPhone,
  FaVenusMars,
  FaBirthdayCake,
  FaShieldAlt,
  FaCalendarAlt,
  FaClock,
  FaEdit,
  FaKey,
  FaFileDownload,
  FaSignOutAlt,
  FaExclamationTriangle,
  FaIdBadge,
  FaCheckDouble,
  FaUserCircle,
  FaInfoCircle,
  FaUserTag,
  FaHashtag,
} from "react-icons/fa";

function Profile() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [medicines, setMedicines] = useState([]);
  const [reminders, setReminders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // ── Modals / toast state ──
  const [showEditModal, setShowEditModal] = useState(false);
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [editForm, setEditForm] = useState({
    full_name: "",
    email: "",
    phone: "",
    gender: "",
    date_of_birth: "",
  });
  const [passwordForm, setPasswordForm] = useState({
    current_password: "",
    new_password: "",
    confirm_password: "",
  });
  const [editError, setEditError] = useState(null);
  const [passwordError, setPasswordError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    const fetchProfileData = async () => {
      try {
        const [profileRes, medRes, remRes] = await Promise.all([
          api.get("accounts/profile/"),
          api.get("medicines/").catch(() => ({ data: [] })),
          api.get("reminders/").catch(() => ({ data: [] })),
        ]);
        setProfile(profileRes.data);
        setMedicines(medRes.data || []);
        setReminders(remRes.data || []);
      } catch (err) {
        console.error("Failed to fetch profile:", err);
        setError("Could not load profile data. Please try again.");
        if (err.response?.status === 401) {
          navigate("/login");
        }
      } finally {
        setLoading(false);
      }
    };
    fetchProfileData();
  }, [navigate]);

  const handleLogout = () => {
    localStorage.removeItem("access");
    localStorage.removeItem("refresh");
    navigate("/login");
  };

  // ── Toast helper ──
  const showToast = (type, message) => {
    setToast({ type, message });
    window.setTimeout(() => setToast(null), 4000);
  };

  // Pull one user-friendly message out of a DRF error response like
  // {"field": ["message"]} or {"non_field_errors": ["message"]}.
  const apiErrorMessage = (err, fallback) => {
    const data = err?.response?.data;
    if (data && typeof data === "object") {
      for (const value of Object.values(data)) {
        if (Array.isArray(value) && value.length > 0) return String(value[0]);
        if (typeof value === "string" && value) return value;
      }
    }
    if (typeof data === "string" && data) return data;
    return fallback;
  };

  // ── Edit Profile ──
  const openEditModal = () => {
    setEditForm({
      // Pre-fill with the real name (first + last, falling back to username
      // where registration stored the full name) so saving persists a proper
      // first/last name.
      full_name: profile?.full_name || profile?.username || "",
      email: profile?.email || "",
      phone: profile?.phone || "",
      gender: profile?.gender_code || "",
      date_of_birth: profile?.date_of_birth || "",
    });
    setEditError(null);
    setShowEditModal(true);
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setEditError(null);
    try {
      const res = await api.patch("accounts/profile/", {
        full_name: editForm.full_name.trim(),
        email: editForm.email.trim(),
        phone: editForm.phone.trim(),
        gender: editForm.gender || "",
        date_of_birth: editForm.date_of_birth || "",
      });
      setProfile(res.data);
      setShowEditModal(false);
      showToast("success", "Profile updated successfully");
    } catch (err) {
      console.error("Failed to update profile:", err);
      setEditError(
        apiErrorMessage(err, "Failed to update profile. Please try again.")
      );
    } finally {
      setSaving(false);
    }
  };

  // ── Change Password ──
  const openPasswordModal = () => {
    setPasswordForm({
      current_password: "",
      new_password: "",
      confirm_password: "",
    });
    setPasswordError(null);
    setShowPasswordModal(true);
  };

  const handlePasswordSubmit = async (e) => {
    e.preventDefault();
    const { current_password, new_password, confirm_password } = passwordForm;

    if (!current_password || !new_password || !confirm_password) {
      setPasswordError("All fields are required.");
      return;
    }
    if (new_password !== confirm_password) {
      setPasswordError("New password and confirm password do not match.");
      return;
    }

    setSaving(true);
    setPasswordError(null);
    try {
      await api.post("accounts/change-password/", passwordForm);
      setShowPasswordModal(false);
      showToast("success", "Password changed successfully");
    } catch (err) {
      console.error("Failed to change password:", err);
      setPasswordError(
        apiErrorMessage(err, "Failed to change password. Please try again.")
      );
    } finally {
      setSaving(false);
    }
  };

  // ── Health Report: built from the user's REAL medicines + reminders ──
  const handleDownloadReport = () => {
    try {
      const medicineName = (id) =>
        medicines.find((m) => m.id === id)?.medicine_name || "Unknown Medicine";

      const lines = [];
      const hr = "══════════════════════════════════════════════";
      lines.push(hr);
      lines.push("            PILLSYNC HEALTH REPORT");
      lines.push(hr);
      lines.push(`Generated: ${new Date().toLocaleString()}`);
      lines.push(`Patient: ${userName}`);
      lines.push(`Username: @${username}`);
      if (isAvailable(email)) lines.push(`Email: ${email}`);
      if (isAvailable(phone)) lines.push(`Phone: ${phone}`);
      lines.push(`Role: ${role}`);
      if (joinedDate) lines.push(`Member Since: ${joinedDate}`);
      lines.push("");

      lines.push("MEDICATIONS");
      lines.push("───────────");
      if (medicines.length === 0) {
        lines.push("No medications recorded.");
      } else {
        medicines.forEach((m, i) => {
          lines.push(
            `${i + 1}. ${m.medicine_name} (${m.dosage || "—"} ${m.medicine_type || ""})`
          );
          lines.push(
            `   Frequency: ${m.frequency || "—"} | Stock: ${m.stock ?? "—"} | Status: ${m.is_active ? "Active" : "Inactive"}`
          );
          if (m.start_date) {
            lines.push(
              `   Period: ${m.start_date} → ${m.end_date || "ongoing"}`
            );
          }
          if (m.instructions) lines.push(`   Instructions: ${m.instructions}`);
        });
      }
      lines.push("");

      lines.push("REMINDERS & ADHERENCE");
      lines.push("─────────────────────");
      if (reminders.length === 0) {
        lines.push("No reminders recorded.");
      } else {
        reminders.forEach((r, i) => {
          lines.push(
            `${i + 1}. ${medicineName(r.medicine)} | ${r.reminder_date || ""} ${r.reminder_time || ""} | ${r.status || "—"}`
          );
        });
      }
      const taken = reminders.filter((r) => r.status === "TAKEN").length;
      const missed = reminders.filter((r) => r.status === "MISSED").length;
      lines.push("");
      lines.push(
        `Adherence: ${taken} taken, ${missed} missed out of ${reminders.length} reminder(s).`
      );
      lines.push(hr);

      const blob = new Blob([lines.join("\n")], {
        type: "text/plain;charset=utf-8",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `PillSync-Health-Report-${username}.txt`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showToast("success", "Health report downloaded");
    } catch (err) {
      console.error("Failed to generate report:", err);
      showToast("error", "Could not generate the report. Please try again.");
    }
  };

  // ── Computed Stats ──
  const totalMedicines = medicines.length;
  const activeReminders = reminders.filter(
    (r) => r.status === "PENDING" || r.status === "Pending"
  ).length;
  const todayReminders = reminders.filter((r) => {
    if (!r.reminder_date) return false;
    const today = new Date().toISOString().split("T")[0];
    return r.reminder_date === today;
  }).length;
  const completedDoses = reminders.filter(
    (r) => r.status === "TAKEN" || r.status === "Taken"
  ).length;

  // ── Helpers ──
  const getInitial = (name) => (name || "U")[0].toUpperCase();

  const formatDate = (dateStr) => {
    if (!dateStr) return null;
    try {
      const opts = {
        year: "numeric",
        month: "long",
        day: "numeric",
      };
      // Date-only strings (YYYY-MM-DD) are parsed as UTC midnight by `new Date`,
      // which can shift the day in negative UTC offsets. Parse them locally.
      if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
        const [y, m, d] = dateStr.split("-").map(Number);
        return new Date(y, m - 1, d).toLocaleDateString("en-US", opts);
      }
      return new Date(dateStr).toLocaleDateString("en-US", opts);
    } catch {
      return dateStr;
    }
  };

  // Date of birth is displayed as DD/MM/YYYY (e.g. 23/04/1992).
  const formatDOB = (dateStr) => {
    if (!dateStr) return null;
    try {
      if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
        const [y, m, d] = dateStr.split("-").map(Number);
        return new Date(y, m - 1, d).toLocaleDateString("en-GB");
      }
      return new Date(dateStr).toLocaleDateString("en-GB");
    } catch {
      return dateStr;
    }
  };

  // Last login is displayed as e.g. "15 Aug 2026, 03:45 AM" (day-first,
  // from the real Django User.last_login value).
  const formatDateTime = (dateStr) => {
    if (!dateStr) return null;
    try {
      const d = new Date(dateStr);
      if (Number.isNaN(d.getTime())) return dateStr;
      const day = String(d.getDate()).padStart(2, "0");
      const month = d.toLocaleString("en-US", { month: "short" });
      const year = d.getFullYear();
      let hours = d.getHours();
      const minutes = String(d.getMinutes()).padStart(2, "0");
      const ampm = hours >= 12 ? "PM" : "AM";
      hours = hours % 12 || 12;
      return `${day} ${month} ${year}, ${String(hours).padStart(2, "0")}:${minutes} ${ampm}`;
    } catch {
      return dateStr;
    }
  };

  const isAvailable = (value) => {
    return value && value !== "" && value !== "None" && value !== "null";
  };

  // ── Skeleton Loading ──
  if (loading) {
    return (
      <div className="dashboard-layout">
        <Sidebar />
        <div className="dashboard-content-wrapper">
          <DashboardTopNav userData={{ username: "User", role: "Patient" }} />
          <div className="dashboard-content">
            <div className="profile-page">
              <div className="profile-skeleton">
                <div className="skeleton-row">
                  <div className="skeleton-avatar" />
                  <div className="skeleton-lines">
                    <div className="skeleton-line skeleton-line-md" />
                    <div className="skeleton-line-sm" />
                    <div className="skeleton-line skeleton-line-md" style={{ width: "50%" }} />
                  </div>
                </div>
              </div>
              <div className="profile-stats-grid">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="profile-stat-card" style={{ opacity: 1, animation: "none" }}>
                    <div style={{ width: 52, height: 52, borderRadius: 14, background: "#e2e8f0", flexShrink: 0 }} />
                    <div style={{ flex: 1 }}>
                      <div className="skeleton-line" style={{ width: "40%", marginBottom: 6 }} />
                      <div className="skeleton-line-sm" />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── Error State ──
  if (error && !profile) {
    return (
      <div className="dashboard-layout">
        <Sidebar />
        <div className="dashboard-content-wrapper">
          <DashboardTopNav userData={{ username: "User", role: "Patient" }} />
          <div className="dashboard-content">
            <div className="profile-page">
              <div className="profile-error">
                <div className="profile-error-icon">
                  <FaExclamationTriangle />
                </div>
                <h2 className="profile-error-title">Oops! Something went wrong</h2>
                <p className="profile-error-message">{error}</p>
                <button
                  className="profile-error-retry-btn"
                  onClick={() => window.location.reload()}
                >
                  Retry
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── User Data ──
  const userName = profile?.full_name || profile?.username || "User";
  const username = profile?.username || "—";
  const email = profile?.email || "—";
  const role = profile?.role || "Patient";
  const joinedDate = formatDate(profile?.date_joined || profile?.created_at);
  const phone = profile?.phone || profile?.phone_number;
  const gender = profile?.gender;
  const dateOfBirth = formatDOB(profile?.date_of_birth || profile?.dob);
  const lastLogin = formatDateTime(profile?.last_login);
  // Registration stores the "Full Name" in the username field, so when no
  // first/last name is set the real name still lives in username. Prefer
  // first + last name, fall back to username (never "Not Available" when
  // real name data exists).
  const fullName = profile?.full_name || profile?.username || "";
  // Verification comes straight from the backend (User.is_verified), so it
  // always reflects the real account state — never hardcoded.
  const isVerified = profile?.is_verified;
  const isActive = profile?.is_active !== undefined ? profile.is_active : true;
  const accountType = role;

  return (
    <div className="dashboard-layout">
      <Sidebar />

      <div className="dashboard-content-wrapper">
        <DashboardTopNav
          userData={{
            username: profile?.username || "User",
            role: profile?.role || "Patient",
          }}
          medicines={medicines}
          reminders={reminders}
        />

        <div className="dashboard-content">
          <div className="profile-page">
            {/* ════════════════════════════════════════════
                PROFILE HEADER CARD
                ════════════════════════════════════════════ */}
            <div className="profile-header-card">
              {/* Avatar */}
              <div className="profile-avatar-wrapper">
                <div className="profile-avatar">
                  {getInitial(userName)}
                </div>
                <div className="profile-online-indicator" title="Online" />
              </div>

              {/* Info */}
              <div className="profile-header-info">
                <h1 className="profile-header-name">{userName}</h1>
                <p className="profile-header-username">@{username}</p>

                <div className="profile-header-details">
                  <div className="profile-header-detail-item">
                    <FaEnvelope className="detail-icon" />
                    {email}
                  </div>

                  {isAvailable(phone) && (
                    <div className="profile-header-detail-item">
                      <FaPhone className="detail-icon" />
                      {phone}
                    </div>
                  )}

                  {joinedDate && (
                    <div className="profile-header-detail-item">
                      <FaCalendarAlt className="detail-icon" />
                      Joined {joinedDate}
                    </div>
                  )}
                </div>

                {/* Role Badge */}
                <div className="profile-role-badge">
                  <FaIdBadge />
                  {role}
                </div>
              </div>
            </div>

            {/* ════════════════════════════════════════════
                STATISTICS SECTION
                ════════════════════════════════════════════ */}
            <div className="profile-stats-grid">
              {/* Total Medicines */}
              <div className="profile-stat-card">
                <div className="profile-stat-icon teal">
                  <FaPills />
                </div>
                <div className="profile-stat-info">
                  <div className="profile-stat-number">{totalMedicines}</div>
                  <div className="profile-stat-label">Total Medicines</div>
                </div>
              </div>

              {/* Active Reminders */}
              <div className="profile-stat-card">
                <div className="profile-stat-icon blue">
                  <FaBell />
                </div>
                <div className="profile-stat-info">
                  <div className="profile-stat-number">{activeReminders}</div>
                  <div className="profile-stat-label">Active Reminders</div>
                </div>
              </div>

              {/* Today's Medicines */}
              <div className="profile-stat-card">
                <div className="profile-stat-icon amber">
                  <FaCalendarCheck />
                </div>
                <div className="profile-stat-info">
                  <div className="profile-stat-number">{todayReminders}</div>
                  <div className="profile-stat-label">Today's Medicines</div>
                </div>
              </div>

              {/* Completed Doses */}
              <div className="profile-stat-card">
                <div className="profile-stat-icon green">
                  <FaCheckCircle />
                </div>
                <div className="profile-stat-info">
                  <div className="profile-stat-number">{completedDoses}</div>
                  <div className="profile-stat-label">Completed Doses</div>
                </div>
              </div>
            </div>

            {/* ════════════════════════════════════════════
                PERSONAL & ACCOUNT INFORMATION
                ════════════════════════════════════════════ */}
            <div className="profile-content-grid">
              {/* Personal Information Card */}
              <div className="profile-info-card">
                <div className="profile-info-card-header">
                  <div className="profile-info-card-header-icon teal-bg">
                    <FaUserCircle />
                  </div>
                  <h3 className="profile-info-card-title">Personal Information</h3>
                </div>

                <div className="profile-info-fields">
                  <div className="profile-info-field full-width">
                    <span className="profile-info-field-label">
                      <FaUser /> Full Name
                    </span>
                    <span className={`profile-info-field-value ${!isAvailable(fullName) ? "not-available" : ""}`}>
                      {isAvailable(fullName) ? (
                        <><FaCheckDouble className="field-value-icon" />{fullName}</>
                      ) : (
                        "Not Available"
                      )}
                    </span>
                  </div>

                  <div className="profile-info-field">
                    <span className="profile-info-field-label">
                      <FaHashtag /> Username
                    </span>
                    <span className="profile-info-field-value">
                      {username}
                    </span>
                  </div>

                  <div className="profile-info-field">
                    <span className="profile-info-field-label">
                      <FaEnvelope /> Email
                    </span>
                    <span className="profile-info-field-value">
                      {email}
                    </span>
                  </div>

                  <div className="profile-info-field">
                    <span className="profile-info-field-label">
                      <FaPhone /> Phone
                    </span>
                    <span className={`profile-info-field-value ${!isAvailable(phone) ? "not-available" : ""}`}>
                      {isAvailable(phone) ? (
                        <><FaPhone className="field-value-icon" />{phone}</>
                      ) : (
                        "Not Available"
                      )}
                    </span>
                  </div>

                  <div className="profile-info-field">
                    <span className="profile-info-field-label">
                      <FaVenusMars /> Gender
                    </span>
                    <span className={`profile-info-field-value ${!isAvailable(gender) ? "not-available" : ""}`}>
                      {isAvailable(gender) ? gender : "Not Available"}
                    </span>
                  </div>

                  <div className="profile-info-field">
                    <span className="profile-info-field-label">
                      <FaBirthdayCake /> Date of Birth
                    </span>
                    <span className={`profile-info-field-value ${!isAvailable(dateOfBirth) ? "not-available" : ""}`}>
                      {isAvailable(dateOfBirth) ? (
                        <><FaBirthdayCake className="field-value-icon" />{dateOfBirth}</>
                      ) : (
                        "Not Available"
                      )}
                    </span>
                  </div>

                  <div className="profile-info-field">
                    <span className="profile-info-field-label">
                      <FaUserTag /> Role
                    </span>
                    <span className="profile-info-field-value">
                      {role}
                    </span>
                  </div>

                  <div className="profile-info-field full-width">
                    <span className="profile-info-field-label">
                      <FaShieldAlt /> Account Status
                    </span>
                    <span className="profile-info-field-value">
                      <span className={`profile-status-badge ${isActive ? "active" : "inactive"}`}>
                        {isActive ? "Active" : "Inactive"}
                      </span>
                    </span>
                  </div>
                </div>
              </div>

              {/* Account Information Card */}
              <div className="profile-info-card">
                <div className="profile-info-card-header">
                  <div className="profile-info-card-header-icon blue-bg">
                    <FaInfoCircle />
                  </div>
                  <h3 className="profile-info-card-title">Account Information</h3>
                </div>

                <div className="profile-info-fields">
                  <div className="profile-info-field full-width">
                    <span className="profile-info-field-label">
                      <FaUserTag /> Account Type
                    </span>
                    <span className="profile-info-field-value">
                      {accountType}
                    </span>
                  </div>

                  <div className="profile-info-field full-width">
                    <span className="profile-info-field-label">
                      <FaShieldAlt /> Verification Status
                    </span>
                    <span className="profile-info-field-value">
                      {isVerified !== undefined ? (
                        <span className={`profile-status-badge ${isVerified ? "verified" : "unverified"}`}>
                          {isVerified ? "Verified" : "Unverified"}
                        </span>
                      ) : (
                        <span className="not-available">Not Available</span>
                      )}
                    </span>
                  </div>

                  <div className="profile-info-field full-width">
                    <span className="profile-info-field-label">
                      <FaCalendarAlt /> Member Since
                    </span>
                    <span className="profile-info-field-value">
                      {joinedDate ? (
                        <><FaCalendarAlt className="field-value-icon" />{joinedDate}</>
                      ) : (
                        <span className="not-available">Not Available</span>
                      )}
                    </span>
                  </div>

                  <div className="profile-info-field full-width">
                    <span className="profile-info-field-label">
                      <FaClock /> Last Login
                    </span>
                    <span className={`profile-info-field-value ${!isAvailable(lastLogin) ? "not-available" : ""}`}>
                      {isAvailable(lastLogin) ? (
                        <><FaClock className="field-value-icon" />{lastLogin}</>
                      ) : (
                        "Not Available"
                      )}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* ════════════════════════════════════════════
                ACTION BUTTONS
                ════════════════════════════════════════════ */}
            <div className="profile-actions-section">
              <h3 className="profile-actions-title">
                <FaEdit /> Quick Actions
              </h3>
              <div className="profile-actions-grid">
                {/* Edit Profile */}
                <button
                  className="profile-action-btn edit"
                  onClick={openEditModal}
                  aria-label="Edit Profile"
                >
                  <div className="action-btn-icon">
                    <FaEdit />
                  </div>
                  <span className="action-btn-label">Edit Profile</span>
                  <span className="action-btn-sub">Update your details</span>
                </button>

                {/* Change Password */}
                <button
                  className="profile-action-btn password"
                  onClick={openPasswordModal}
                  aria-label="Change Password"
                >
                  <div className="action-btn-icon">
                    <FaKey />
                  </div>
                  <span className="action-btn-label">Change Password</span>
                  <span className="action-btn-sub">Update security</span>
                </button>

                {/* Download Health Report */}
                <button
                  className="profile-action-btn report"
                  onClick={handleDownloadReport}
                  aria-label="Download Health Report"
                >
                  <div className="action-btn-icon">
                    <FaFileDownload />
                  </div>
                  <span className="action-btn-label">Health Report</span>
                  <span className="action-btn-sub">Download report</span>
                </button>

                {/* Logout */}
                <button
                  className="profile-action-btn logout-action"
                  onClick={handleLogout}
                  aria-label="Logout"
                >
                  <div className="action-btn-icon">
                    <FaSignOutAlt />
                  </div>
                  <span className="action-btn-label">Logout</span>
                  <span className="action-btn-sub">Sign out safely</span>
                </button>
              </div>
            </div>

            {/* ── Toast notification ── */}
            {toast && (
              <div className={`profile-toast ${toast.type}`} role="status">
                {toast.type === "success" ? (
                  <FaCheckCircle />
                ) : (
                  <FaExclamationTriangle />
                )}
                <span>{toast.message}</span>
              </div>
            )}

            {/* ── Edit Profile Modal ── */}
            {showEditModal && (
              <div
                className="profile-modal-overlay"
                onClick={() => setShowEditModal(false)}
              >
                <div
                  className="profile-modal"
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="profile-modal-header">
                    <div className="profile-modal-header-icon">
                      <FaEdit />
                    </div>
                    <h3>Edit Profile</h3>
                    <button
                      type="button"
                      className="profile-modal-close"
                      onClick={() => setShowEditModal(false)}
                      aria-label="Close"
                    >
                      ×
                    </button>
                  </div>
                  <form
                    onSubmit={handleEditSubmit}
                    className="profile-modal-form"
                  >
                    <div className="profile-modal-field">
                      <label htmlFor="edit-full-name">Full Name</label>
                      <input
                        id="edit-full-name"
                        type="text"
                        value={editForm.full_name}
                        onChange={(e) =>
                          setEditForm({
                            ...editForm,
                            full_name: e.target.value,
                          })
                        }
                        placeholder="Your full name"
                      />
                    </div>
                    <div className="profile-modal-field">
                      <label htmlFor="edit-email">Email</label>
                      <input
                        id="edit-email"
                        type="email"
                        value={editForm.email}
                        onChange={(e) =>
                          setEditForm({ ...editForm, email: e.target.value })
                        }
                        placeholder="you@example.com"
                        required
                      />
                    </div>
                    <div className="profile-modal-field">
                      <label htmlFor="edit-phone">Phone</label>
                      <input
                        id="edit-phone"
                        type="tel"
                        value={editForm.phone}
                        onChange={(e) =>
                          setEditForm({ ...editForm, phone: e.target.value })
                        }
                        placeholder="10-digit Indian mobile number"
                      />
                    </div>
                    <div className="profile-modal-field">
                      <label htmlFor="edit-gender">Gender</label>
                      <select
                        id="edit-gender"
                        value={editForm.gender}
                        onChange={(e) =>
                          setEditForm({ ...editForm, gender: e.target.value })
                        }
                      >
                        <option value="">Prefer not to say</option>
                        <option value="MALE">Male</option>
                        <option value="FEMALE">Female</option>
                        <option value="OTHER">Other</option>
                        <option value="PREFER_NOT_TO_SAY">Prefer not to say</option>
                      </select>
                    </div>
                    <div className="profile-modal-field">
                      <label htmlFor="edit-dob">Date of Birth</label>
                      <input
                        id="edit-dob"
                        type="date"
                        value={editForm.date_of_birth}
                        onChange={(e) =>
                          setEditForm({
                            ...editForm,
                            date_of_birth: e.target.value,
                          })
                        }
                        max={new Date().toISOString().split("T")[0]}
                      />
                    </div>
                    {editError && (
                      <p className="profile-form-error">{editError}</p>
                    )}
                    <div className="profile-modal-actions">
                      <button
                        type="button"
                        className="profile-modal-btn cancel"
                        onClick={() => setShowEditModal(false)}
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        className="profile-modal-btn save"
                        disabled={saving}
                      >
                        {saving ? "Saving..." : "Save Changes"}
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            )}

            {/* ── Change Password Modal ── */}
            {showPasswordModal && (
              <div
                className="profile-modal-overlay"
                onClick={() => setShowPasswordModal(false)}
              >
                <div
                  className="profile-modal"
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="profile-modal-header">
                    <div className="profile-modal-header-icon password">
                      <FaKey />
                    </div>
                    <h3>Change Password</h3>
                    <button
                      type="button"
                      className="profile-modal-close"
                      onClick={() => setShowPasswordModal(false)}
                      aria-label="Close"
                    >
                      ×
                    </button>
                  </div>
                  <form
                    onSubmit={handlePasswordSubmit}
                    className="profile-modal-form"
                  >
                    <div className="profile-modal-field">
                      <label htmlFor="pw-current">Current Password</label>
                      <input
                        id="pw-current"
                        type="password"
                        value={passwordForm.current_password}
                        onChange={(e) =>
                          setPasswordForm({
                            ...passwordForm,
                            current_password: e.target.value,
                          })
                        }
                        placeholder="Enter current password"
                        autoComplete="current-password"
                      />
                    </div>
                    <div className="profile-modal-field">
                      <label htmlFor="pw-new">New Password</label>
                      <input
                        id="pw-new"
                        type="password"
                        value={passwordForm.new_password}
                        onChange={(e) =>
                          setPasswordForm({
                            ...passwordForm,
                            new_password: e.target.value,
                          })
                        }
                        placeholder="Enter new password"
                        autoComplete="new-password"
                      />
                    </div>
                    <div className="profile-modal-field">
                      <label htmlFor="pw-confirm">Confirm New Password</label>
                      <input
                        id="pw-confirm"
                        type="password"
                        value={passwordForm.confirm_password}
                        onChange={(e) =>
                          setPasswordForm({
                            ...passwordForm,
                            confirm_password: e.target.value,
                          })
                        }
                        placeholder="Re-enter new password"
                        autoComplete="new-password"
                      />
                    </div>
                    {passwordError && (
                      <p className="profile-form-error">{passwordError}</p>
                    )}
                    <div className="profile-modal-actions">
                      <button
                        type="button"
                        className="profile-modal-btn cancel"
                        onClick={() => setShowPasswordModal(false)}
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        className="profile-modal-btn save"
                        disabled={saving}
                      >
                        {saving ? "Updating..." : "Change Password"}
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default Profile;
