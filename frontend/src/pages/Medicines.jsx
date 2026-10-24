import Navbar from "../components/Navbar";
import "./Medicines.css";
import { useState, useEffect, useCallback, useRef } from "react";
import api from "../services/api";

import {
  FaPills,
  FaPlus,
  FaSearch,
  FaHeartbeat,
  FaClock,
  FaUsers,
  FaFileMedical,
  FaEdit,
  FaTrash,
  FaSpinner,
} from "react-icons/fa";

const today = () => new Date().toISOString().split("T")[0];
const futureDate = (days) => {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().split("T")[0];
};

function Medicines() {
  const [medicines, setMedicines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState({ type: "", text: "" });

  const [newMedicine, setNewMedicine] = useState({
    medicine: "",
    disease: "",
    dosage: "",
    schedule: "",
    dailyDoseCount: "1",
    status: "Active",
  });

  const [showForm, setShowForm] = useState(false);
  const [search, setSearch] = useState("");
  const [filterSchedule, setFilterSchedule] = useState("All");
  const [editId, setEditId] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [medicineNameError, setMedicineNameError] = useState("");
  const formRef = useRef(null);

  const showToast = useCallback((type, text) => {
    setToast({ type, text });
    setTimeout(() => setToast({ type: "", text: "" }), 4000);
  }, []);

  const defaultProfiles = [
    { id: 1, name: "Anjali", role: "Primary User" },
    { id: 2, name: "Mother", role: "Family Profile" },
    { id: 3, name: "Father", role: "Family Profile" },
  ];

  const [profiles, setProfiles] = useState(() => {
    const saved = localStorage.getItem("profiles");
    return saved ? JSON.parse(saved) : defaultProfiles;
  });

  const [newProfile, setNewProfile] = useState({
    name: "",
    role: "",
  });

  const [showProfileForm, setShowProfileForm] = useState(false);

  const [prescription, setPrescription] = useState(() => {
    return localStorage.getItem("prescription") || "";
  });

  const [selectedFile, setSelectedFile] = useState(null);
  const [fileURL, setFileURL] = useState("");

  /* ========== Fetch medicines from API ========== */
  const fetchMedicines = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get("medicines/");
      setMedicines(response.data);
    } catch (error) {
      console.error("Failed to fetch medicines:", error);
      const status = error.response?.status;
      const detail = error.response?.data?.detail;
      if (status === 401) {
        showToast("error", "Session expired. Please log in again.");
      } else if (status === 500) {
        showToast("error", "Server error. Please try again later.");
      } else {
        showToast(
          "error",
          detail || `Failed to load medicines (HTTP ${status || "network error"})`
        );
      }
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    fetchMedicines();
  }, [fetchMedicines]);

  // When the Edit pencil is clicked, the form renders ABOVE the medicine
  // table (outside the current viewport). Scroll it into view so the user
  // sees it open with the selected medicine's data prefilled.
  useEffect(() => {
    if (showForm && isEditing) {
      formRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [showForm, isEditing]);

  useEffect(() => {
    localStorage.setItem("profiles", JSON.stringify(profiles));
  }, [profiles]);

  useEffect(() => {
    if (prescription) {
      localStorage.setItem("prescription", prescription);
    }
  }, [prescription]);

  const handleFileChange = (e) => {
    setSelectedFile(e.target.files[0]);
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    // Clear validation error when the user edits the medicine name field
    if (name === "medicine" && medicineNameError) {
      setMedicineNameError("");
    }
    setNewMedicine({
      ...newMedicine,
      [name]: value,
    });
  };

  const resetForm = () => {
    setNewMedicine({
      medicine: "",
      disease: "",
      dosage: "",
      schedule: "",
      dailyDoseCount: "1",
      status: "Active",
    });
    setMedicineNameError("");
    setEditId(null);
    setIsEditing(false);
    setShowForm(false);
  };

  /* ========== Add / Update Medicine via API ========== */
  const addMedicine = async () => {
    if (
      !newMedicine.medicine ||
      !newMedicine.disease ||
      !newMedicine.dosage ||
      !newMedicine.schedule ||
      !newMedicine.dailyDoseCount
    ) {
      alert("Please fill all fields");
      return;
    }

    setSaving(true);

    const payload = {
      medicine_name: newMedicine.medicine,
      dosage: newMedicine.dosage,
      frequency: newMedicine.schedule,
      frequency_doses_per_day: parseInt(newMedicine.dailyDoseCount, 10) || 1,
      medicine_type: "TABLET",
      is_active: newMedicine.status === "Active",
      instructions: newMedicine.disease,
      stock: 0,
      start_date: today(),
      end_date: futureDate(30),
      source: "manual",
    };

    try {
      if (isEditing && editId) {
        // Partial update: only send the fields the form edits, so the
        // update never resets stock, prescription dates or medicine type.
        await api.patch(`medicines/${editId}/`, {
          medicine_name: newMedicine.medicine,
          dosage: newMedicine.dosage,
          frequency: newMedicine.schedule,
          frequency_doses_per_day: parseInt(newMedicine.dailyDoseCount, 10) || 1,
          is_active: newMedicine.status === "Active",
          instructions: newMedicine.disease,
        });
        showToast("success", "Medicine updated successfully");
      } else {
        await api.post("medicines/", payload);
        showToast("success", "Medicine added successfully");
      }

      await fetchMedicines();
      setMedicineNameError("");
      resetForm();
    } catch (error) {
      const status = error.response?.status;
      const responseData = error.response?.data;

      console.error("Medicine save error:", status, responseData);

      if (status === 401) {
        showToast("error", "Session expired. Please log in again.");
      } else if (status === 403) {
        showToast("error", "Permission denied. Please log in again.");
      } else if (status === 400 && responseData?.message) {
        // Backend validation message (duplicate, invalid name, etc.)
        setMedicineNameError(responseData.message);
      } else if (status === 503 && responseData?.message) {
        setMedicineNameError(responseData.message);
      } else {
        const msg =
          responseData?.medicine_name?.[0] ||
          responseData?.detail ||
          responseData?.message ||
          `Failed to save medicine (HTTP ${status || "network error"}).`;
        showToast("error", msg);
      }
    } finally {
      setSaving(false);
    }
  };

  const editMedicine = (item) => {
    setNewMedicine({
      medicine: item.medicine_name || "",
      disease: item.instructions || "",
      dosage: item.dosage || "",
      schedule: item.frequency || "",
      dailyDoseCount: String(item.frequency_doses_per_day || 1),
      status: item.is_active ? "Active" : "Pending",
    });
    setMedicineNameError("");
    setEditId(item.id);
    setIsEditing(true);
    setShowForm(true);
  };

  /* ========== Delete Medicine via API ========== */
  const deleteMedicine = async (id) => {
    const confirmed = window.confirm(
      "Are you sure you want to delete this medicine?"
    );
    if (!confirmed) return;

    setSaving(true);
    try {
      await api.delete(`medicines/${id}/`);
      showToast("success", "Medicine deleted successfully");
      await fetchMedicines();
    } catch (error) {
      console.error("Medicine delete error:", error.response?.status, error.response?.data);
      const status = error.response?.status;
      const detail = error.response?.data?.detail;
      if (status === 401) {
        showToast("error", "Session expired. Please log in again.");
      } else {
        showToast("error", detail || `Failed to delete medicine (HTTP ${status || "network error"})`);
      }
    } finally {
      setSaving(false);
    }
  };

  const addProfile = () => {
    if (!newProfile.name || !newProfile.role) {
      alert("Please fill all fields");
      return;
    }

    setProfiles([
      ...profiles,
      { id: Date.now(), ...newProfile },
    ]);

    setNewProfile({ name: "", role: "" });
    setShowProfileForm(false);
  };

  const deleteProfile = (id) => {
    if (window.confirm("Delete this profile?")) {
      setProfiles(profiles.filter((item) => item.id !== id));
    }
  };

  const uploadPrescription = () => {
    if (!selectedFile) {
      alert("Please select a file");
      return;
    }

    setPrescription(selectedFile.name);
    setFileURL(URL.createObjectURL(selectedFile));
    setSelectedFile(null);
    alert("Prescription uploaded successfully!");
  };

  const deletePrescription = () => {
    if (window.confirm("Delete prescription?")) {
      setPrescription("");
      setFileURL("");
      localStorage.removeItem("prescription");
    }
  };

  const diseases = [...new Set(medicines.map((item) => item.instructions || "General"))];

  const morningMedicines = medicines.filter(
    (item) => item.frequency === "Morning"
  );
  const afternoonMedicines = medicines.filter(
    (item) => item.frequency === "Afternoon"
  );
  const nightMedicines = medicines.filter(
    (item) => item.frequency === "Night"
  );

  return (
    <>
      <Navbar />

      {/* Toast Messages */}
      {toast.text && (
        <div className={`message-toast ${toast.type}`}>
          {toast.text}
        </div>
      )}

      <div className="medicine-page">
        {/* Header */}
        <div className="medicine-header">
          <div>
            <h1>Medicine Management</h1>
            <p>
              Manage medicines, dosage schedules, diseases and prescriptions
              from one place.
            </p>
          </div>
          <button
            className="add-btn"
            onClick={() => {
              if (!showForm) resetForm();
              setShowForm((prev) => !prev);
            }}
          >
            <FaPlus />
            Add Medicine
          </button>
        </div>

        {/* Search */}
        <div className="top-controls">
          <div className="search-box">
            <FaSearch className="search-icon" />
            <input
              type="text"
              placeholder="Search medicines..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="filter-box">
            <select
              value={filterSchedule}
              onChange={(e) => setFilterSchedule(e.target.value)}
            >
              <option value="All">All Schedules</option>
              <option value="Morning">Morning</option>
              <option value="Afternoon">Afternoon</option>
              <option value="Night">Night</option>
            </select>
          </div>
        </div>

        {showForm && (
          <div className="add-form" ref={formRef}>
            <h2>{isEditing ? "Edit Medicine" : "Add New Medicine"}</h2>

            <div className="medicine-name-field">
              <input
                type="text"
                name="medicine"
                placeholder="Medicine Name"
                value={newMedicine.medicine}
                onChange={handleChange}
                className={medicineNameError ? "input-error" : ""}
              />
              {medicineNameError && (
                <span className="validation-error">
                  ❌ {medicineNameError}
                </span>
              )}
            </div>
            <input
              type="text"
              name="disease"
              placeholder="Disease"
              value={newMedicine.disease}
              onChange={handleChange}
            />
            <input
              type="text"
              name="dosage"
              placeholder="Dosage"
              value={newMedicine.dosage}
              onChange={handleChange}
            />
            <input
              type="text"
              name="schedule"
              placeholder="Schedule (e.g. Morning/Afternoon/Night)"
              value={newMedicine.schedule}
              onChange={handleChange}
            />
            <select
              name="dailyDoseCount"
              value={newMedicine.dailyDoseCount}
              onChange={handleChange}
              required
            >
              <option value="1">1 time/day</option>
              <option value="2">2 times/day</option>
              <option value="3">3 times/day</option>
              <option value="4">4 times/day</option>
            </select>
            <button onClick={addMedicine} disabled={saving}>
              {saving ? (
                <><FaSpinner style={{ marginRight: 6 }} /> Saving...</>
              ) : isEditing ? (
                "Update Medicine"
              ) : (
                "Save Medicine"
              )}
            </button>
          </div>
        )}

        {/* Feature Cards */}
        <div className="feature-grid">
          <div className="feature-card">
            <FaPills className="card-icon" />
            <h3>Medicine Management</h3>
            <p>Add, update and organize all prescribed medicines.</p>
          </div>
          <div className="feature-card">
            <FaHeartbeat className="card-icon" />
            <h3>Disease Tracking</h3>
            <p>Monitor diseases and associated medications.</p>
          </div>
          <div className="feature-card">
            <FaClock className="card-icon" />
            <h3>Dosage Scheduling</h3>
            <p>Track medicine timings for morning, afternoon and night.</p>
          </div>
          <div className="feature-card">
            <FaUsers className="card-icon" />
            <h3>Multiple Profiles</h3>
            <p>Manage medicines for family members from one dashboard.</p>
          </div>
          <div className="feature-card">
            <FaFileMedical className="card-icon" />
            <h3>Prescription Management</h3>
            <p>Upload and organize digital prescriptions securely.</p>
          </div>
        </div>

        {/* Medicine Table */}
        <div className="table-card">
          <div className="table-title">
            <h2>
              Medicine List
              <span className="medicine-count">
                ({medicines.length})
              </span>
            </h2>
          </div>

          {loading ? (
            <div style={{ textAlign: "center", padding: "40px" }}>
              <FaSpinner className="spinner-icon" />
              <p>Loading medicines...</p>
            </div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Medicine</th>
                  <th>Disease</th>
                  <th>Dosage</th>
                  <th>Schedule</th>
                  <th>Frequency</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {medicines
                  .filter((item) => {
                    const matchSearch = (item.medicine_name || "")
                      .toLowerCase()
                      .includes(search.toLowerCase());

                    const matchSchedule =
                      filterSchedule === "All" ||
                      (item.frequency || "") === filterSchedule;

                    return matchSearch && matchSchedule;
                  })
                  .map((item) => (
                    <tr key={item.id}>
                      <td>{item.medicine_name}</td>
                      <td>{item.instructions || "—"}</td>
                      <td>{item.dosage}</td>
                      <td>{item.frequency}</td>
                      <td>{item.frequency_doses_per_day ? `${item.frequency_doses_per_day}x/day` : "—"}</td>
                      <td>
                        <span className={`status ${item.is_active ? "Active" : "Pending"}`}>
                          {item.is_active ? "Active" : "Pending"}
                        </span>
                      </td>
                      <td>
                        <button
                          className="edit-btn"
                          onClick={() => editMedicine(item)}
                        >
                          <FaEdit />
                        </button>
                        <button
                          className="delete-btn"
                          onClick={() => deleteMedicine(item.id)}
                        >
                          <FaTrash />
                        </button>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Bottom Section */}
        <div className="bottom-grid">
          {/* Disease Tracking */}
          <div className="info-card">
            <h2>Disease Tracking</h2>
            {diseases.map((disease, index) => (
              <div key={index}>
                <div className="disease-item">
                  <div>
                    <h4>{disease}</h4>
                    <p>
                      {
                        medicines.filter(
                          (item) => (item.instructions || "General") === disease
                        ).length
                      } Medicine(s)
                    </p>
                  </div>
                  <span className="badge green">Active</span>
                </div>
                <div className="progress">
                  <div
                    className="progress-fill"
                    style={{
                      width: `${Math.min(
                        medicines.filter(
                          (item) => (item.instructions || "General") === disease
                        ).length * 25,
                        100
                      )}%`,
                    }}
                  ></div>
                </div>
              </div>
            ))}
          </div>

          {/* Dosage Scheduling */}
          <div className="info-card">
            <h2>Dosage Scheduling</h2>
            <div className="schedule">
              <div className="schedule-box">
                <h4> Morning</h4>
                {morningMedicines.length > 0 ? (
                  morningMedicines.map((item) => (
                    <p key={item.id}> {item.medicine_name}</p>
                  ))
                ) : (
                  <p>No medicines</p>
                )}
              </div>
              <div className="schedule-box">
                <h4>☀ Afternoon</h4>
                {afternoonMedicines.length > 0 ? (
                  afternoonMedicines.map((item) => (
                    <p key={item.id}> {item.medicine_name}</p>
                  ))
                ) : (
                  <p>No medicines</p>
                )}
              </div>
              <div className="schedule-box">
                <h4> Night</h4>
                {nightMedicines.length > 0 ? (
                  nightMedicines.map((item) => (
                    <p key={item.id}> {item.medicine_name}</p>
                  ))
                ) : (
                  <p>No medicines</p>
                )}
              </div>
            </div>
          </div>

          {/* Multiple Profiles */}
          <div className="info-card">
            <h2>Multiple Profiles</h2>
            <button
              className="add-btn"
              style={{ marginBottom: "20px" }}
              onClick={() => setShowProfileForm(!showProfileForm)}
            >
              <FaPlus /> Add Profile
            </button>

            {showProfileForm && (
              <div className="add-form">
                <input
                  type="text"
                  placeholder="Profile Name"
                  value={newProfile.name}
                  onChange={(e) =>
                    setNewProfile({ ...newProfile, name: e.target.value })
                  }
                />
                <input
                  type="text"
                  placeholder="Role"
                  value={newProfile.role}
                  onChange={(e) =>
                    setNewProfile({ ...newProfile, role: e.target.value })
                  }
                />
                <button onClick={addProfile}>Save Profile</button>
              </div>
            )}

            {profiles.map((profile) => (
              <div className="profile" key={profile.id}>
                <div className="avatar">
                  {profile.name.charAt(0).toUpperCase()}
                </div>
                <div style={{ flex: 1 }}>
                  <h4>{profile.name}</h4>
                  <p>{profile.role}</p>
                </div>
                <button
                  className="delete-btn"
                  onClick={() => deleteProfile(profile.id)}
                >
                  <FaTrash />
                </button>
              </div>
            ))}
          </div>

          {/* Prescription Management */}
          <div className="info-card">
            <h2>Prescription Management</h2>
            <div className="upload-box">
              <FaFileMedical className="upload-icon" />
              <h3>Upload Prescription</h3>
              <p>Select a PDF or Image file.</p>
              <input
                type="file"
                accept=".pdf,.jpg,.jpeg,.png"
                onChange={handleFileChange}
              />
              <br /><br />
              <button className="upload-btn" onClick={uploadPrescription}>
                Upload File
              </button>

              {prescription && (
                <div style={{ marginTop: "20px" }}>
                  <h4>Uploaded File</h4>
                  <p>{prescription}</p>
                  {fileURL && (
                    <button
                      className="upload-btn"
                      style={{ marginTop: "10px", marginRight: "10px" }}
                      onClick={() => window.open(fileURL, "_blank")}
                    >
                      👁 View Prescription
                    </button>
                  )}
                  <button className="delete-btn" onClick={deletePrescription}>
                    <FaTrash /> Delete
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

export default Medicines;
