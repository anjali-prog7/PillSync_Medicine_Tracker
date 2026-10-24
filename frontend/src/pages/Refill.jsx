import { useState, useEffect, useCallback } from "react";
import {
  FaCalendarAlt,
  FaExclamationTriangle,
  FaCheckCircle,
  FaPills,
  FaClock,
  FaMedkit,
  FaSpinner,
  FaEnvelope,
  FaPlus,
  FaCheck,
} from "react-icons/fa";
import { useNavigate } from "react-router-dom";

import Sidebar from "../components/Sidebar";
import DashboardTopNav from "../components/DashboardTopNav";
import api from "../services/api";
import "../styles/Refill.css";

function Refill() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refillData, setRefillData] = useState(null);
  const navigate = useNavigate();

  // Manual refill state
  const [selectedMedicineId, setSelectedMedicineId] = useState("");
  const [refillQuantity, setRefillQuantity] = useState("");
  const [refillSubmitting, setRefillSubmitting] = useState(false);
  const [refillSuccess, setRefillSuccess] = useState("");

  const fetchRefillData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await api.get("medicines/refill/");
      setRefillData(response.data);
    } catch (err) {
      console.error("Failed to fetch refill data:", err);
      setError("Unable to load refill information. Please try again.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Defer initial fetch to avoid synchronous setState within effect body
    const timer = setTimeout(fetchRefillData, 0);
    return () => clearTimeout(timer);
  }, [fetchRefillData]);

  // Clear success message after 5 seconds
  useEffect(() => {
    if (!refillSuccess) return;
    const timer = setTimeout(() => setRefillSuccess(""), 5000);
    return () => clearTimeout(timer);
  }, [refillSuccess]);

  const formatDate = (dateStr) => {
    if (!dateStr) return "N/A";
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-GB", {
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  };

  const getStatusColor = (status) => {
    switch (status) {
      case "URGENT":
        return "refill-status-urgent";
      case "REFILL_SOON":
        return "refill-status-soon";
      case "NO_REFILL_NEEDED":
        return "refill-status-safe";
      default:
        return "";
    }
  };

  const getStatusLabel = (status) => {
    switch (status) {
      case "URGENT":
        return "URGENT REFILL";
      case "REFILL_SOON":
        return "REFILL NEEDED SOON";
      case "NO_REFILL_NEEDED":
        return "NO REFILL NEEDED";
      default:
        return status;
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case "URGENT":
        return <FaExclamationTriangle />;
      case "REFILL_SOON":
        return <FaClock />;
      case "NO_REFILL_NEEDED":
        return <FaCheckCircle />;
      default:
        return <FaPills />;
    }
  };

  if (loading) {
    return (
      <div className="refill-layout">
        <Sidebar />
        <div className="refill-content-wrapper">
          <DashboardTopNav />
          <div className="refill-content">
            <div className="refill-inner">
              <div className="refill-loading">
                <FaSpinner className="refill-loading-spinner" />
                <p>Loading refill information...</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="refill-layout">
        <Sidebar />
        <div className="refill-content-wrapper">
          <DashboardTopNav />
          <div className="refill-content">
            <div className="refill-inner">
              <div className="refill-error">
                <FaExclamationTriangle className="refill-error-icon" />
                <p>{error}</p>
                <button onClick={fetchRefillData} className="refill-retry-btn">
                  Try Again
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!refillData || !refillData.medicines || refillData.medicines.length === 0) {
    return (
      <div className="refill-layout">
        <Sidebar />
        <div className="refill-content-wrapper">
          <DashboardTopNav />
          <div className="refill-content">
            <div className="refill-inner">
              <div className="refill-page-header">
                <div>
                  <div className="refill-page-title">
                    <span className="refill-page-title-icon">
                      <FaCalendarAlt />
                    </span>
                    Refill Tracker
                  </div>
                  <p className="refill-page-subtitle">
                    Monitor medicine stock and get alerts when refills are needed.
                  </p>
                </div>
              </div>
              <div className="refill-empty-state">
                <div className="refill-empty-icon">
                  <FaPills />
                </div>
                <h3>No medicines added yet</h3>
                <p>Add a medicine to start tracking refill requirements.</p>
                <button
                  onClick={() => navigate("/medicines")}
                  className="refill-add-medicine-btn"
                >
                  <FaMedkit /> Add Medicine
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const { summary, urgent, refill_soon, no_refill } = refillData;

  const handleManualRefill = async (e) => {
    e.preventDefault();
    if (!selectedMedicineId || !refillQuantity) return;

    const qty = parseInt(refillQuantity, 10);
    if (isNaN(qty) || qty <= 0) return;

    try {
      setRefillSubmitting(true);
      setRefillSuccess("");

      // Find the current medicine to get its stock
      const currentMedicine = refillData.medicines.find(
        (m) => String(m.id) === String(selectedMedicineId)
      );
      if (!currentMedicine) return;

      // PATCH the medicine's stock — adds the refilled quantity to current stock
      const newStock = currentMedicine.current_stock + qty;
      await api.patch(`medicines/${selectedMedicineId}/`, {
        stock: newStock,
      });

      // Reset form
      setSelectedMedicineId("");
      setRefillQuantity("");
      setRefillSuccess("Medicine stock updated successfully.");

      // Refresh refill data so calculations update
      await fetchRefillData();
    } catch (err) {
      console.error("Failed to update medicine stock:", err);
    } finally {
      setRefillSubmitting(false);
    }
  };

  return (
    <div className="refill-layout">
      <Sidebar />
      <div className="refill-content-wrapper">
        <DashboardTopNav />
        <div className="refill-content">
          <div className="refill-inner">
            {/* Page Header */}
            <div className="refill-page-header">
              <div>
                <div className="refill-page-title">
                  <span className="refill-page-title-icon">
                    <FaCalendarAlt />
                  </span>
                  Refill Tracker
                </div>
                <p className="refill-page-subtitle">
                  Monitor medicine stock and get alerts when refills are needed.
                </p>
              </div>
              <span className="refill-header-badge">
                <FaPills /> {summary.total_medicines} Medicine{summary.total_medicines !== 1 ? "s" : ""}
              </span>
            </div>

            {/* Status Summary Cards */}
            <div className="refill-status-cards">
              {/* No Refill Needed */}
              <div className="refill-status-card refill-status-safe">
                <div className="refill-status-card-icon">
                  <FaCheckCircle />
                </div>
                <div className="refill-status-card-content">
                  <h3>{summary.no_refill_count}</h3>
                  <p>No Refill Needed</p>
                </div>
                <div className="refill-status-card-indicator"></div>
              </div>

              {/* Refill Needed Soon */}
              <div className="refill-status-card refill-status-soon">
                <div className="refill-status-card-icon">
                  <FaClock />
                </div>
                <div className="refill-status-card-content">
                  <h3>{summary.refill_soon_count}</h3>
                  <p>Refill Needed Soon</p>
                </div>
                <div className="refill-status-card-indicator"></div>
              </div>

              {/* Urgent Refill */}
              <div className="refill-status-card refill-status-urgent">
                <div className="refill-status-card-icon">
                  <FaExclamationTriangle />
                </div>
                <div className="refill-status-card-content">
                  <h3>{summary.urgent_count}</h3>
                  <p>Urgent Refill</p>
                </div>
                <div className="refill-status-card-indicator"></div>
              </div>
            </div>

            {/* Urgent Section */}
            {urgent.length > 0 && (
              <div className="refill-section">
                <div className="refill-section-header refill-section-urgent">
                  <FaExclamationTriangle />
                  <h2>Urgent Refill ({urgent.length})</h2>
                  <span className="refill-section-badge urgent">
                    Stock critically low
                  </span>
                </div>
                {urgent.length > 4 ? (
                  <div className="refill-medicine-scroll-container">
                    {urgent.map((medicine) => (
                      <MedicineCard
                        key={medicine.id}
                        medicine={medicine}
                        formatDate={formatDate}
                        getStatusLabel={getStatusLabel}
                        getStatusIcon={getStatusIcon}
                        getStatusColor={getStatusColor}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="refill-medicine-grid refill-no-scroll">
                    {urgent.map((medicine) => (
                      <MedicineCard
                        key={medicine.id}
                        medicine={medicine}
                        formatDate={formatDate}
                        getStatusLabel={getStatusLabel}
                        getStatusIcon={getStatusIcon}
                        getStatusColor={getStatusColor}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Refill Soon Section */}
            {refill_soon.length > 0 && (
              <div className="refill-section">
                <div className="refill-section-header refill-section-soon">
                  <FaClock />
                  <h2>Refill Needed Soon ({refill_soon.length})</h2>
                  <span className="refill-section-badge soon">
                    Stock getting low
                  </span>
                </div>
                {refill_soon.length > 4 ? (
                  <div className="refill-medicine-scroll-container">
                    {refill_soon.map((medicine) => (
                      <MedicineCard
                        key={medicine.id}
                        medicine={medicine}
                        formatDate={formatDate}
                        getStatusLabel={getStatusLabel}
                        getStatusIcon={getStatusIcon}
                        getStatusColor={getStatusColor}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="refill-medicine-grid refill-no-scroll">
                    {refill_soon.map((medicine) => (
                      <MedicineCard
                        key={medicine.id}
                        medicine={medicine}
                        formatDate={formatDate}
                        getStatusLabel={getStatusLabel}
                        getStatusIcon={getStatusIcon}
                        getStatusColor={getStatusColor}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* No Refill Section */}
            {no_refill.length > 0 && (
              <div className="refill-section">
                <div className="refill-section-header refill-section-safe">
                  <FaCheckCircle />
                  <h2>No Refill Needed ({no_refill.length})</h2>
                  <span className="refill-section-badge safe">
                    Sufficient stock
                  </span>
                </div>
                {no_refill.length > 4 ? (
                  <div className="refill-medicine-scroll-container">
                    {no_refill.map((medicine) => (
                      <MedicineCard
                        key={medicine.id}
                        medicine={medicine}
                        formatDate={formatDate}
                        getStatusLabel={getStatusLabel}
                        getStatusIcon={getStatusIcon}
                        getStatusColor={getStatusColor}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="refill-medicine-grid refill-no-scroll">
                    {no_refill.map((medicine) => (
                      <MedicineCard
                        key={medicine.id}
                        medicine={medicine}
                        formatDate={formatDate}
                        getStatusLabel={getStatusLabel}
                        getStatusIcon={getStatusIcon}
                        getStatusColor={getStatusColor}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Manual Refill Section */}
            <div className="refill-manual-section">
              <div className="refill-manual-section-header">
                <div className="refill-manual-section-title">
                  <span className="refill-manual-section-title-icon">
                    <FaPlus />
                  </span>
                  Manual Refill
                </div>
              </div>
              <p className="refill-manual-section-subtitle">
                Update your medicine stock after purchasing a refill.
              </p>

              <form
                className="refill-manual-refill-card"
                onSubmit={handleManualRefill}
              >
                <div className="refill-manual-refill-form">
                  <div className="refill-manual-field">
                    <label htmlFor="refill-medicine">Medicine</label>
                    <select
                      id="refill-medicine"
                      value={selectedMedicineId}
                      onChange={(e) => setSelectedMedicineId(e.target.value)}
                      required
                    >
                      <option value="">Select Medicine</option>
                      {refillData.medicines.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.medicine_name} — {m.dosage}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="refill-manual-field">
                    <label htmlFor="refill-qty">Refilled Quantity</label>
                    <input
                      id="refill-qty"
                      type="number"
                      min="1"
                      placeholder="e.g. 20"
                      value={refillQuantity}
                      onChange={(e) => setRefillQuantity(e.target.value)}
                      required
                    />
                    <span className="refill-quantity-suffix">tablets</span>
                  </div>

                  <button
                    type="submit"
                    className="refill-manual-submit-btn"
                    disabled={
                      refillSubmitting || !selectedMedicineId || !refillQuantity
                    }
                  >
                    {refillSubmitting ? (
                      <>
                        <FaSpinner className="refill-loading-spinner" style={{ fontSize: 15, animation: "refill-spin 1s linear infinite" }} />
                        Updating...
                      </>
                    ) : (
                      <>
                        <FaCheck />
                        Update Stock
                      </>
                    )}
                  </button>
                </div>
              </form>

              {refillSuccess && (
                <div className="refill-success-message">
                  <FaCheckCircle />
                  <span>{refillSuccess}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function MedicineCard({
  medicine,
  formatDate,
  getStatusLabel,
  getStatusIcon,
  getStatusColor,
}) {
  const statusColor = getStatusColor(medicine.refill_status);

  return (
    <div className={`refill-medicine-card ${statusColor}`}>
      <div className="refill-medicine-card-header">
        <div className="refill-medicine-icon">
          <FaPills />
        </div>
        <div className="refill-medicine-info">
          <h3>{medicine.medicine_name}</h3>
          <span className="refill-medicine-type">{medicine.medicine_type}</span>
        </div>
        <div className={`refill-medicine-status-badge ${statusColor}`}>
          {getStatusIcon(medicine.refill_status)}
          <span>{getStatusLabel(medicine.refill_status)}</span>
        </div>
      </div>

      <div className="refill-medicine-card-body">
        <div className="refill-medicine-stats">
          <div className="refill-medicine-stat">
            <span className="refill-stat-label">Remaining Stock</span>
            <span className="refill-stat-value">
              {medicine.current_stock} <span className="refill-stat-unit">{medicine.dosage}</span>
            </span>
          </div>
          <div className="refill-medicine-stat">
            <span className="refill-stat-label">Daily Consumption</span>
            <span className="refill-stat-value">
              {medicine.daily_consumption} <span className="refill-stat-unit">{medicine.dosage}/day</span>
            </span>
          </div>
          <div className="refill-medicine-stat">
            <span className="refill-stat-label">Days Remaining</span>
            <span className="refill-stat-value">
              {medicine.days_remaining} <span className="refill-stat-unit">days</span>
            </span>
          </div>
          <div className="refill-medicine-stat">
            <span className="refill-stat-label">Estimated Depletion</span>
            <span className="refill-stat-value refill-date">
              {formatDate(medicine.depletion_date)}
            </span>
          </div>
        </div>

        {medicine.depletion_days <= 2 && (
          <div className="refill-medicine-email-alert">
            <FaEnvelope />
            <span>Refill email sent to your registered email address</span>
          </div>
        )}
      </div>
    </div>
  );
}

export default Refill;
