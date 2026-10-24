import { useState, useRef, useEffect, useCallback } from 'react';
import Sidebar from '../components/Sidebar';
import DashboardTopNav from '../components/DashboardTopNav';
import api from '../services/api';
import '../styles/PrescriptionOcr.css';
import {
  EMPTY_FORM,
  saveFormState, restoreFormState,
  saveOCRState, restoreOCRState,
  saveImage, restoreImage, dataUrlToFile,
} from '../utils/ocrPersistence';

import {
  FaCamera, FaUpload, FaFileMedical, FaFilePdf, FaImage,
  FaTimes, FaCheckCircle, FaExclamationTriangle, FaSpinner,
  FaTrash, FaDownload, FaEye, FaSearch, FaFlask, FaUserMd,
  FaHospital, FaCalendarAlt, FaClipboardList, FaPills, FaClock,
  FaDisease, FaNotesMedical, FaSave, FaEraser, FaCheckDouble,
  FaArrowRight, FaInfoCircle, FaListUl, FaFileAlt,
  FaPrescriptionBottle, FaHistory, FaEdit, FaCode, FaUser,
  FaBarcode, FaQrcode, FaExclamationCircle, FaStethoscope,
} from 'react-icons/fa';

const SUPPORTED_IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/jpg'];
const SUPPORTED_FILE_TYPES = [...SUPPORTED_IMAGE_TYPES, 'application/pdf'];
const MAX_FILE_SIZE = 10 * 1024 * 1024;

const FREQUENCY_OPTIONS = [
  { value: 'Morning', label: 'Morning' },
  { value: 'Afternoon', label: 'Afternoon' },
  { value: 'Night', label: 'Night' },
];

const TIMING_OPTIONS = [
  'Before Food', 'After Food', 'With Food', 'Empty Stomach', 'Morning', 'Night',
];

const MEDICINE_TYPES = [
  { value: 'TABLET', label: 'Tablet' },
  { value: 'CAPSULE', label: 'Capsule' },
  { value: 'SYRUP', label: 'Syrup' },
  { value: 'INJECTION', label: 'Injection' },
];

/* ==========================================================
   Confidence meter (90-100 green, 70-89 yellow, below 70 red)
   ========================================================== */
function ConfidenceMeter({ value }) {
  const conf = Number(value) || 0;
  const level = conf >= 90 ? 'high' : conf >= 70 ? 'medium' : 'low';
  const color = level === 'high' ? '#16A34A' : level === 'medium' ? '#F59E0B' : '#DC2626';
  const pct = Math.min(100, Math.max(0, conf));
  return (
    <div className={`confidence-meter ${level}`}>
      <div className="confidence-meter-gauge" style={{ background: `conic-gradient(${color} ${pct * 3.6}deg, #E2E8F0 0deg)` }}>
        <div className="confidence-meter-inner">
          <span className="confidence-meter-value" style={{ color }}>{conf}%</span>
          <span className="confidence-meter-label">{level}</span>
        </div>
      </div>
    </div>
  );
}

/* ==========================================================
   Medicine card with Edit / Delete / Apply actions
   ========================================================== */
function MedicineCard({ medicine, index, editing, onEdit, onDelete, onApply }) {
  const [draft, setDraft] = useState({ ...medicine });

  // Keep the local draft in sync when the parent updates the medicine object.
  // eslint-disable-next-line react-hooks/set-state-in-effect -- documented "adjust state when props change" pattern
  useEffect(() => setDraft({ ...medicine }), [medicine]);

  const field = (label, value, icon) => (
    <div className="med-card-field">
      <span className="med-card-field-label">{icon} {label}</span>
      <span className="med-card-field-value">{value || 'Not Available'}</span>
    </div>
  );

  if (editing) {
    return (
      <div className="med-card editing">
        <div className="med-card-head">
          <div className="med-card-title">
            <span className="med-card-index">{index + 1}</span>
            <strong>Edit Medicine</strong>
          </div>
          <span className="med-card-badge badge-edit">Editing</span>
        </div>
        <div className="med-edit-grid">
          {[
            ['medicine_name', 'Medicine Name'],
            ['brand', 'Brand'],
            ['generic_name', 'Generic Name'],
            ['strength', 'Strength'],
            ['unit', 'Unit'],
            ['dosage', 'Dosage'],
            ['quantity', 'Quantity'],
            ['frequency', 'Frequency'],
            ['timing', 'Timing'],
            ['duration', 'Duration'],
            ['route', 'Route'],
            ['special_instructions', 'Special Instructions'],
          ].map(([key, label]) => (
            <div className="form-group" key={key}>
              <label>{label}</label>
              {key === 'timing' ? (
                <select value={draft[key] || ''} onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}>
                  <option value="">Select timing</option>
                  {TIMING_OPTIONS.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              ) : (
                <input
                  type="text"
                  value={draft[key] || ''}
                  placeholder={label}
                  onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
                />
              )}
            </div>
          ))}
          <div className="form-group">
            <label>Confidence (%)</label>
            <input type="number" min="0" max="100" value={draft.confidence ?? 0} onChange={(e) => setDraft({ ...draft, confidence: e.target.value })} />
          </div>
        </div>
        <div className="med-card-actions">
          <button className="ocr-btn primary" onClick={() => onEdit(draft)}><FaCheckCircle /> Save</button>
          <button className="ocr-btn secondary" onClick={() => onEdit(null)}><FaTimes /> Cancel</button>
        </div>
      </div>
    );
  }

  return (
    <div className="med-card">
      <div className="med-card-head">
        <div className="med-card-title">
          <span className="med-card-index">{index + 1}</span>
          <div>
            <strong className="med-card-name">{medicine.medicine_name || 'Unknown Medicine'}</strong>
            {(medicine.brand || medicine.generic_name) && (
              <span className="med-card-subtitle">
                {[medicine.brand, medicine.generic_name].filter(Boolean).join(' · ')}
              </span>
            )}
          </div>
        </div>
        <span className={`med-card-confidence ${(medicine.confidence || 0) >= 90 ? 'high' : (medicine.confidence || 0) >= 70 ? 'medium' : 'low'}`}>
          {medicine.confidence || 0}%
        </span>
      </div>
      <div className="med-card-fields">
        {(medicine.strength || medicine.unit) && field('Strength', `${medicine.strength || ''}${medicine.unit ? ' ' + medicine.unit : ''}`.trim(), <FaFlask />)}
        {field('Dosage', medicine.dosage, <FaPills />)}
        {field('Frequency', medicine.frequency, <FaClock />)}
        {field('Timing', medicine.timing, <FaClock />)}
        {field('Duration', medicine.duration, <FaCalendarAlt />)}
        {field('Quantity', medicine.quantity, <FaListUl />)}
        {field('Route', medicine.route, <FaStethoscope />)}
        {field('Special Instructions', medicine.special_instructions, <FaNotesMedical />)}
      </div>
      <div className="med-card-actions">
        <button className="ocr-btn primary" onClick={() => onApply(medicine)}><FaArrowRight /> Apply to Entry Form</button>
        <button className="ocr-btn secondary" onClick={() => onEdit({ ...medicine })}><FaEdit /> Edit</button>
        <button className="ocr-btn danger" onClick={() => onDelete(index)}><FaTrash /> Delete</button>
      </div>
    </div>
  );
}

/* ==========================================================
   Restored-upload helpers
   (rebuild a File / preview from what was persisted in localStorage)
   ========================================================== */
function restoreUploadedFile(which) {
  const stored = restoreImage(which);
  if (!stored) return null;
  if (stored.pdf || !stored.dataUrl) {
    // Non-image files (e.g. PDF prescriptions) only have metadata persisted —
    // rebuild a placeholder File so the name/section still shows, but a
    // re-extract needs a fresh upload (empty file => Extract is disabled).
    try {
      return new File([new Blob()], stored.fileName || "uploaded-file", {
        type: stored.fileType || "application/pdf",
      });
    } catch {
      return null;
    }
  }
  return dataUrlToFile(stored.dataUrl, stored.fileName, stored.fileType);
}

function restoreUploadedPreview(which) {
  const stored = restoreImage(which);
  return stored && !stored.pdf && stored.dataUrl ? stored.dataUrl : null;
}

/* ==========================================================
   Main page
   ========================================================== */
function PrescriptionOcr() {
  const [userData, setUserData] = useState({ username: "User", role: "Patient" });
  const [medicines, setMedicines] = useState([]);
  const [reminders] = useState([]);

  // Restore previously uploaded files + previews from localStorage.
  const [medicineFile, setMedicineFile] = useState(() => restoreUploadedFile("medicine"));
  const [medicinePreview, setMedicinePreview] = useState(() => restoreUploadedPreview("medicine"));
  const [prescriptionFile, setPrescriptionFile] = useState(() => restoreUploadedFile("prescription"));
  const [prescriptionPreview, setPrescriptionPreview] = useState(() => restoreUploadedPreview("prescription"));
  // Upload progress is fully isolated per upload section so that extraction on one
  // card never moves the progress bar of the other card.
  const [medicineUploadProgress, setMedicineUploadProgress] = useState(0);
  const [prescriptionUploadProgress, setPrescriptionUploadProgress] = useState(0);

  // Restore the last OCR result + medicine cards after a refresh.
  const [ocrResult, setOcrResult] = useState(() => restoreOCRState().ocrResult);
  const [editableMedicines, setEditableMedicines] = useState(() => restoreOCRState().editableMedicines);
  const [editingIndex, setEditingIndex] = useState(null);

  // Loading (extracting) state is also per-section: only the card that
  // triggered extraction shows its own loading spinner.
  const [medicineOcrLoading, setMedicineOcrLoading] = useState(false);
  const [prescriptionOcrLoading, setPrescriptionOcrLoading] = useState(false);
  const [ocrError, setOcrError] = useState(null);

  // JSON viewer toggle for the extracted result.
  const [showJson, setShowJson] = useState(false);

  // Restore the manual entry form from localStorage (survives refresh).
  const [formData, setFormData] = useState(() => restoreFormState());
  const [savingManual, setSavingManual] = useState(false);

  const [uploadHistory, setUploadHistory] = useState(() => {
    try {
      const saved = localStorage.getItem("pillSync_ocr_history");
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [historySearch, setHistorySearch] = useState("");
  const [historyFilter, setHistoryFilter] = useState("All");
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 5;

  const medicineInputRef = useRef(null);
  const prescriptionInputRef = useRef(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [medRes, profileRes] = await Promise.all([
          api.get("medicines/").catch(() => ({ data: [] })),
          api.get("accounts/profile/").catch(() => null),
        ]);
        setMedicines(medRes.data);
        if (profileRes?.data) {
          setUserData({ username: profileRes.data.username || "User", role: profileRes.data.role || "Patient" });
        }
      } catch { /* offline or auth error — the page still renders */ }
    };
    fetchData();
  }, []);

  const persistHistory = useCallback((history) => {
    localStorage.setItem("pillSync_ocr_history", JSON.stringify(history));
  }, []);

  const todayStr = () => new Date().toISOString().split("T")[0];
  const futureDateStr = (days) => {
    const d = new Date();
    d.setDate(d.getDate() + days);
    return d.toISOString().split("T")[0];
  };
  const nowStr = () => new Date().toLocaleString();
  const na = (v) => (v && String(v).trim()) ? String(v).trim() : "Not Available";

  const handleMedicineFileSelect = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (!SUPPORTED_IMAGE_TYPES.includes(file.type)) { alert("Please select a valid image (PNG, JPG, JPEG)."); return; }
    if (file.size > MAX_FILE_SIZE) { alert("File too large. Maximum size is 10 MB."); return; }
    setMedicineFile(file);
    const reader = new FileReader();
    reader.onload = () => {
      setMedicinePreview(reader.result);
      saveImage("medicine", { dataUrl: reader.result, fileName: file.name, fileType: file.type });
    };
    reader.readAsDataURL(file);
  };

  const handleDropMedicine = (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (!file) return;
    if (!SUPPORTED_IMAGE_TYPES.includes(file.type)) { alert("Please select a valid image (PNG, JPG, JPEG)."); return; }
    if (file.size > MAX_FILE_SIZE) { alert("File too large. Maximum size is 10 MB."); return; }
    setMedicineFile(file);
    const reader = new FileReader();
    reader.onload = () => {
      setMedicinePreview(reader.result);
      saveImage("medicine", { dataUrl: reader.result, fileName: file.name, fileType: file.type });
    };
    reader.readAsDataURL(file);
  };

  const clearMedicineFile = () => {
    setMedicineFile(null); setMedicinePreview(null);
    saveImage("medicine", null);
    if (medicineInputRef.current) medicineInputRef.current.value = "";
  };

  const handlePrescriptionFileSelect = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (!SUPPORTED_FILE_TYPES.includes(file.type)) { alert("Please select a valid file (PDF, PNG, JPG, JPEG)."); return; }
    if (file.size > MAX_FILE_SIZE) { alert("File too large. Maximum size is 10 MB."); return; }
    setPrescriptionFile(file);
    if (SUPPORTED_IMAGE_TYPES.includes(file.type)) {
      const reader = new FileReader();
      reader.onload = () => {
        setPrescriptionPreview(reader.result);
        saveImage("prescription", { dataUrl: reader.result, fileName: file.name, fileType: file.type });
      };
      reader.readAsDataURL(file);
    } else {
      setPrescriptionPreview(null);
      saveImage("prescription", { dataUrl: null, fileName: file.name, fileType: file.type });
    }
  };

  const handleDropPrescription = (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (!file) return;
    if (!SUPPORTED_FILE_TYPES.includes(file.type)) { alert("Please select a valid file (PDF, PNG, JPG, JPEG)."); return; }
    if (file.size > MAX_FILE_SIZE) { alert("File too large. Maximum size is 10 MB."); return; }
    setPrescriptionFile(file);
    if (SUPPORTED_IMAGE_TYPES.includes(file.type)) {
      const reader = new FileReader();
      reader.onload = () => {
        setPrescriptionPreview(reader.result);
        saveImage("prescription", { dataUrl: reader.result, fileName: file.name, fileType: file.type });
      };
      reader.readAsDataURL(file);
    } else {
      setPrescriptionPreview(null);
      saveImage("prescription", { dataUrl: null, fileName: file.name, fileType: file.type });
    }
  };

  const clearPrescriptionFile = () => {
    setPrescriptionFile(null); setPrescriptionPreview(null);
    saveImage("prescription", null);
    if (prescriptionInputRef.current) prescriptionInputRef.current.value = "";
  };

  const triggerOcr = async (file, type) => {
    if (!file) return;
    // One extraction at a time: ignore a trigger while the other section
    // is already extracting, so the two cards never run concurrently and the
    // shared result card can't be raced.
    if (medicineOcrLoading || prescriptionOcrLoading) return;
    const isMedicine = type === "medicine";
    const setSectionProgress = isMedicine ? setMedicineUploadProgress : setPrescriptionUploadProgress;
    const setSectionLoading = isMedicine ? setMedicineOcrLoading : setPrescriptionOcrLoading;
    setOcrError(null); setOcrResult(null); setEditableMedicines([]);
    setEditingIndex(null); setShowJson(false);
    setSectionLoading(true);
    setSectionProgress(0);
    const pi = setInterval(() => {
      setSectionProgress((prev) => { if (prev >= 90) { clearInterval(pi); return 90; } return prev + Math.random() * 15; });
    }, 300);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("upload_type", type);
      const res = await api.post("medicines/prescription/upload/", fd, {
        headers: { "Content-Type": "multipart/form-data" }, timeout: 90000,
      });
      clearInterval(pi); setSectionProgress(100); setTimeout(() => setSectionProgress(0), 800);
      const data = res.data;
      setOcrResult(data);
      // Populate the editable medicine list from the merged result.
      const meds = Array.isArray(data.medicines) && data.medicines.length
        ? data.medicines
        : (data.medicine_name ? [{ medicine_name: data.medicine_name, dosage: data.dosage, quantity: data.quantity, frequency: data.frequency }] : []);
      setEditableMedicines(meds);
      // Persist the result + medicine cards so a refresh restores everything.
      saveOCRState(data, meds);
      // Only VERIFIED results are stored in upload history.
      if (data.status === "success" || data.status === "low_confidence") {
        const entry = {
          id: Date.now(), fileName: file.name, fileType: file.type,
          uploadDate: nowStr(),
          ocrStatus: data.status === "success" ? "Completed" : "Low Confidence",
          medicineCount: meds.length, medicineName: meds[0]?.medicine_name || "-",
          dosage: data.dosage || "-", confidence: data.confidence || 0,
        };
        setUploadHistory((prev) => { const u = [entry, ...prev]; persistHistory(u); return u; });
      }
    } catch (err) {
      clearInterval(pi); setSectionProgress(0);
      const msg = err.response?.data?.error || err.message || "Extraction processing failed.";
      setOcrError(msg);
      setOcrResult({ status: "error", message: msg, medicine_name: "-", dosage: "-", quantity: "-", frequency: "-", doctor_name: "-", hospital: "-", confidence: 0, prescription_details: "", disease: "", prescription_date: "" });
      // Do not persist failed/empty extractions.
      saveOCRState(null, []);
    } finally { setSectionLoading(false); }
  };

  const handleFormChange = (e) => {
    const next = { ...formData, [e.target.name]: e.target.value };
    setFormData(next);
    saveFormState(next);
  };

  const handleSaveManual = async () => {
    const { medicine_name, dosage, frequency } = formData;
    if (!medicine_name || !dosage || !frequency) { alert("Please fill in Medicine Name, Dosage, and Frequency."); return; }
    setSavingManual(true);
    try {
      await api.post("medicines/", {
        medicine_name, dosage, frequency, medicine_type: formData.medicine_type, is_active: true,
        stock: parseInt(formData.quantity) || 0,
        instructions: [formData.disease, formData.timing && `Timing: ${formData.timing}`, formData.duration && `Duration: ${formData.duration}`, formData.prescription_notes].filter(Boolean).join("\n"),
        start_date: formData.start_date || todayStr(), end_date: formData.end_date || futureDateStr(30),
        source: "manual",
      });
      alert("Medicine saved successfully!");
      const emptyForm = { ...EMPTY_FORM };
      setFormData(emptyForm);
      saveFormState(emptyForm);
      const res = await api.get("medicines/").catch(() => ({ data: [] }));
      setMedicines(res.data);
    } catch (err) { alert(err.response?.data?.detail || "Failed to save medicine."); }
    finally { setSavingManual(false); }
  };

  const handleClearForm = () => {
    const emptyForm = { ...EMPTY_FORM };
    setFormData(emptyForm);
    saveFormState(emptyForm);
  };

  /* ==========================================================
     Apply an extracted medicine to the manual entry form
     (auto-fills name, dosage, frequency, timing, duration, quantity)
     ========================================================== */
  const applyOcrToForm = (med) => {
    if (!ocrResult || ocrResult.status === "error" || ocrResult.status === "no_medicine") return;
    const m = med || editableMedicines[0] || {};
    let freq = m.frequency || ocrResult.frequency || "";
    const lower = freq.toLowerCase();
    if (lower.includes("morning")) freq = "Morning";
    else if (lower.includes("afternoon") || lower.includes("lunch")) freq = "Afternoon";
    else if (lower.includes("night") || lower.includes("evening") || lower.includes("dinner")) freq = "Night";
    const next = {
      medicine_name: m.medicine_name || ocrResult.medicine_name || "",
      dosage: m.dosage || ocrResult.dosage || "",
      quantity: m.quantity || ocrResult.quantity || "",
      frequency: freq,
      timing: m.timing || "",
      duration: m.duration || "",
      disease: ocrResult.disease || ocrResult.diagnosis || "",
      doctor_name: ocrResult.doctor?.name || ocrResult.doctor_name || "",
      prescription_notes: (m.special_instructions || ocrResult.prescription_details || ""),
      start_date: todayStr(),
      end_date: futureDateStr(30),
      medicine_type: (ocrResult.medicine_details?.medicine_type || "TABLET").toUpperCase(),
    };
    setFormData(next);
    saveFormState(next);
    document.getElementById("manual-entry-card")?.scrollIntoView({ behavior: "smooth" });
  };

  /* ---- Per-medicine edit / delete --------------------------------- */
  const handleEditMedicine = (draft) => {
    if (draft === null) { setEditingIndex(null); return; }
    const next = editableMedicines.map((m, i) => (i === editingIndex ? draft : m));
    setEditableMedicines(next);
    saveOCRState(ocrResult, next);
    setEditingIndex(null);
  };

  const handleDeleteMedicine = (index) => {
    if (!window.confirm("Remove this medicine from the extracted result?")) return;
    const next = editableMedicines.filter((_, i) => i !== index);
    setEditableMedicines(next);
    saveOCRState(ocrResult, next);
    setEditingIndex(null);
  };

  const deleteHistoryItem = (id) => {
    if (!window.confirm("Delete this history item?")) return;
    setUploadHistory((prev) => { const u = prev.filter((i) => i.id !== id); persistHistory(u); return u; });
  };

  const downloadHistoryItem = (item) => {
    const blob = new Blob([JSON.stringify({ fileName: item.fileName, uploadDate: item.uploadDate, medicineName: item.medicineName, dosage: item.dosage, confidence: item.confidence, status: item.ocrStatus }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = "ocr-result-" + item.id + ".json"; a.click();
    URL.revokeObjectURL(url);
  };

  const filteredHistory = uploadHistory.filter((item) => {
    return item.fileName?.toLowerCase().includes(historySearch.toLowerCase()) &&
      (historyFilter === "All" || item.ocrStatus === historyFilter);
  });

  const totalPages = Math.max(1, Math.ceil(filteredHistory.length / itemsPerPage));
  const paginatedHistory = filteredHistory.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage);

  // Defensive clamp: if history shrinks below the current page, reset it.
  // eslint-disable-next-line react-hooks/set-state-in-effect -- safe one-shot page clamp
  useEffect(() => { if (currentPage > totalPages) setCurrentPage(totalPages); }, [totalPages, currentPage]);

  const renderConfidenceBadge = (c) => {
    if (c >= 90) return <span className="ocr-badge badge-success">High</span>;
    if (c >= 70) return <span className="ocr-badge badge-warning">Medium</span>;
    return <span className="ocr-badge badge-danger">Low</span>;
  };

  const renderStatusBadge = (status) => {
    const map = {
      success: <span className="ocr-badge badge-success"><FaCheckCircle /> Extracted</span>,
      low_confidence: <span className="ocr-badge badge-warning"><FaExclamationTriangle /> Low Confidence</span>,
      no_medicine: <span className="ocr-badge badge-danger"><FaTimes /> No Medicine</span>,
      error: <span className="ocr-badge badge-danger"><FaTimes /> Failed</span>,
    };
    return map[status] || <span className="ocr-badge">{status}</span>;
  };

  // Which uploaded preview to show in the result card.
  const resultPreview = medicinePreview || prescriptionPreview || null;

  return (
    <div className="ocr-layout">
      <Sidebar />
      <div className="ocr-content-wrapper">
        <DashboardTopNav userData={userData} medicines={medicines} reminders={reminders} />
        <div className="ocr-content">
          {/* Header */}
          <div className="ocr-header">
            <div className="ocr-header-left">
              <div className="ocr-header-icon"><FaFileMedical /></div>
              <div>
                <h1>Prescription OCR & Medicine Upload</h1>
                <p>Upload medicine images or prescriptions and automatically extract information using AI Vision (Gemini) with OCR fallback.</p>
              </div>
            </div>
            <div className="ocr-header-right">
              <div className="ocr-stat"><FaUpload /><span>{uploadHistory.length} Uploads</span></div>
              <div className="ocr-stat"><FaPills /><span>{medicines.length} Medicines</span></div>
            </div>
          </div>

          <div className="ocr-cards-grid">
            {/* Card 1: Medicine Upload */}
            <div className="ocr-card fade-in">
              <div className="ocr-card-header">
                <div className="ocr-card-header-left">
                  <div className="ocr-card-icon pill-icon"><FaPills /></div>
                  <div><h2>Medicine Upload</h2><p>Upload medicine strip, bottle or box image</p></div>
                </div>
              </div>
              <div className="ocr-card-body">
                <div className={`drop-zone ${medicinePreview ? "has-preview" : ""}`}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={handleDropMedicine}
                  onClick={() => !medicineFile && medicineInputRef.current?.click()}>
                  <input ref={medicineInputRef} type="file" accept="image/png,image/jpeg,image/jpg" onChange={handleMedicineFileSelect} hidden />
                  {medicinePreview ? (
                    <div className="preview-container">
                      <img src={medicinePreview} alt="Medicine preview" className="preview-image" />
                      <div className="preview-overlay">
                        <span className="preview-file-name">{medicineFile?.name}</span>
                        <div className="preview-actions">
                          <button className="preview-btn" onClick={(e) => { e.stopPropagation(); triggerOcr(medicineFile, "medicine"); }} disabled={medicineOcrLoading}>
                            {medicineOcrLoading ? <FaSpinner className="spin" /> : <FaCamera />} Extract Info
                          </button>
                          <button className="preview-btn danger" onClick={(e) => { e.stopPropagation(); clearMedicineFile(); }}><FaTimes /> Remove</button>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="drop-zone-empty">
                      <div className="drop-zone-icon"><FaUpload /></div>
                      <h3>Upload Medicine Image</h3>
                      <p>Drag & drop or click to browse</p>
                      <span className="drop-zone-formats">PNG, JPG, JPEG | Max 10 MB</span>
                    </div>
                  )}
                </div>
                {medicineUploadProgress > 0 && (
                  <div className="upload-progress-bar">
                    <div className="progress-track"><div className="progress-fill" style={{ width: `${medicineUploadProgress}%` }}></div></div>
                    <span className="progress-text">{Math.round(medicineUploadProgress)}%</span>
                  </div>
                )}
              </div>
            </div>

            {/* Card 2: Prescription Upload */}
            <div className="ocr-card fade-in">
              <div className="ocr-card-header">
                <div className="ocr-card-header-left">
                  <div className="ocr-card-icon prescription-icon"><FaFileMedical /></div>
                  <div><h2>Prescription Upload</h2><p>Upload doctor prescription</p></div>
                </div>
              </div>
              <div className="ocr-card-body">
                <div className={'drop-zone ' + (prescriptionPreview ? "has-preview" : "")}  onDragOver={(e) => e.preventDefault()} onDrop={handleDropPrescription} onClick={() => !prescriptionFile && prescriptionInputRef.current?.click()}>
                  <input ref={prescriptionInputRef} type="file" accept=".pdf,image/png,image/jpeg,image/jpg" onChange={handlePrescriptionFileSelect} hidden />
                  {prescriptionPreview ? (
                    <div className="preview-container">
                      <img src={prescriptionPreview} alt="Prescription preview" className="preview-image" />
                      <div className="preview-overlay">
                        <span className="preview-file-name">{prescriptionFile?.name}</span>
                        <div className="preview-actions">
                          <button className="preview-btn" onClick={(e) => { e.stopPropagation(); triggerOcr(prescriptionFile, "prescription"); }} disabled={prescriptionOcrLoading}>
                            {prescriptionOcrLoading ? <FaSpinner className="spin" /> : <FaCamera />} Extract Info
                          </button>
                          <button className="preview-btn danger" onClick={(e) => { e.stopPropagation(); clearPrescriptionFile(); }}><FaTimes /> Remove</button>
                        </div>
                      </div>
                    </div>
                  ) : prescriptionFile && prescriptionFile.type === "application/pdf" ? (
                    <div className="preview-container pdf-preview">
                      <div className="pdf-icon-large"><FaFilePdf /></div>
                      <div className="pdf-name">{prescriptionFile.name}</div>
                      <div className="preview-overlay">
                        <div className="preview-actions">
                          <button className="preview-btn" onClick={(e) => { e.stopPropagation(); triggerOcr(prescriptionFile, "prescription"); }} disabled={prescriptionOcrLoading || (prescriptionFile && prescriptionFile.size === 0)} title={prescriptionFile && prescriptionFile.size === 0 ? "Upload the PDF again to re-extract" : undefined}>
                            {prescriptionOcrLoading ? <FaSpinner className="spin" /> : <FaCamera />} Extract Info
                          </button>
                          <button className="preview-btn danger" onClick={(e) => { e.stopPropagation(); clearPrescriptionFile(); }}><FaTimes /> Remove</button>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="drop-zone-empty">
                      <div className="drop-zone-icon"><FaFileMedical /></div>
                      <h3>Upload Prescription</h3>
                      <p>Drag & drop or click to browse</p>
                      <span className="drop-zone-formats">PDF, PNG, JPG, JPEG | Max 10 MB</span>
                    </div>
                  )}
                </div>
                {prescriptionUploadProgress > 0 && (
                  <div className="upload-progress-bar">
                    <div className="progress-track"><div className="progress-fill" style={{ width: '' + prescriptionUploadProgress + "%" }}></div></div>
                    <span className="progress-text">{Math.round(prescriptionUploadProgress)}%</span>
                  </div>
                )}
              </div>
            </div>

            {/* Card 3: Manual Medicine Entry */}
            <div className="ocr-card fade-in" id="manual-entry-card">
              <div className="ocr-card-header">
                <div className="ocr-card-header-left">
                  <div className="ocr-card-icon form-icon"><FaClipboardList /></div>
                  <div><h2>Manual Medicine Entry</h2><p>Enter medicine details manually</p></div>
                </div>
              </div>
              <div className="ocr-card-body">
                <div className="manual-form-grid">
                  <div className="form-group">
                    <label><FaPills /> Medicine Name <span className="required">*</span></label>
                    <input type="text" name="medicine_name" placeholder="e.g. Paracetamol 650mg" value={formData.medicine_name} onChange={handleFormChange} />
                  </div>
                  <div className="form-group">
                    <label><FaFlask /> Dosage <span className="required">*</span></label>
                    <input type="text" name="dosage" placeholder="e.g. 650 mg" value={formData.dosage} onChange={handleFormChange} />
                  </div>
                  <div className="form-group">
                    <label><FaListUl /> Quantity</label>
                    <input type="number" name="quantity" placeholder="e.g. 10" value={formData.quantity} onChange={handleFormChange} />
                  </div>
                  <div className="form-group">
                    <label><FaClock /> Frequency <span className="required">*</span></label>
                    <select name="frequency" value={formData.frequency} onChange={handleFormChange}>
                      <option value="">Select frequency</option>
                      {FREQUENCY_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label><FaClock /> Timing</label>
                    <select name="timing" value={formData.timing} onChange={handleFormChange}>
                      <option value="">Select timing</option>
                      {TIMING_OPTIONS.map((o) => <option key={o} value={o}>{o}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label><FaCalendarAlt /> Duration</label>
                    <input type="text" name="duration" placeholder="e.g. 5 days" value={formData.duration} onChange={handleFormChange} />
                  </div>
                  <div className="form-group">
                    <label><FaDisease /> Disease</label>
                    <input type="text" name="disease" placeholder="e.g. Fever & Cold" value={formData.disease} onChange={handleFormChange} />
                  </div>
                  <div className="form-group">
                    <label><FaUserMd /> Doctor Name</label>
                    <input type="text" name="doctor_name" placeholder="e.g. Dr. Sharma" value={formData.doctor_name} onChange={handleFormChange} />
                  </div>
                  <div className="form-group">
                    <label><FaCalendarAlt /> Start Date</label>
                    <input type="date" name="start_date" value={formData.start_date} onChange={handleFormChange} />
                  </div>
                  <div className="form-group">
                    <label><FaCalendarAlt /> End Date</label>
                    <input type="date" name="end_date" value={formData.end_date} onChange={handleFormChange} />
                  </div>
                  <div className="form-group">
                    <label><FaPrescriptionBottle /> Medicine Type</label>
                    <select name="medicine_type" value={formData.medicine_type} onChange={handleFormChange}>
                      {MEDICINE_TYPES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </select>
                  </div>
                  <div className="form-group full-width">
                    <label><FaNotesMedical /> Prescription Notes</label>
                    <textarea name="prescription_notes" placeholder="Any additional notes..." value={formData.prescription_notes} onChange={handleFormChange} rows={3} />
                  </div>
                </div>
                <div className="form-actions">
                  <button className="ocr-btn primary" onClick={handleSaveManual} disabled={savingManual}>
                    {savingManual ? <><FaSpinner className="spin" /> Saving...</> : <><FaSave /> Save Medicine</>}
                  </button>
                  <button className="ocr-btn secondary" onClick={handleClearForm}><FaEraser /> Clear Form</button>
                </div>
              </div>
            </div>

            {/* Card 4: AI Recognition Result */}
            <div className="ocr-card fade-in">
              <div className="ocr-card-header">
                <div className="ocr-card-header-left">
                  <div className="ocr-card-icon result-icon"><FaCheckDouble /></div>
                  <div><h2>AI Recognition Result</h2><p>Extracted information from uploaded file</p></div>
                </div>
                {ocrResult && ocrResult.status !== "error" && ocrResult.status !== "no_medicine" && (
                  <div className="ocr-confidence-display">
                    <span className="confidence-score">{ocrResult.confidence}%</span>
                    <span className="confidence-label">Confidence</span>
                  </div>
                )}
              </div>
              <div className="ocr-card-body">
                {(medicineOcrLoading || prescriptionOcrLoading) ? (
                  <div className="ocr-loading-state">
                    <div className="ocr-loading-spinner"><FaCamera /></div>
                    <h3>Analyzing Image with AI...</h3>
                    <p>Our AI (Gemini Vision) is understanding your file. If needed, it falls back to OCR and merges both results.</p>
                    <div className="upload-progress-bar full">
                      <div className="progress-track"><div className="progress-fill" style={{ width: `${medicineOcrLoading ? medicineUploadProgress : prescriptionUploadProgress}%` }}></div></div>
                      <span className="progress-text">{Math.round(medicineOcrLoading ? medicineUploadProgress : prescriptionUploadProgress)}%</span>
                    </div>
                    <div className="loading-skeleton">
                      <div className="skeleton-line w-60"></div>
                      <div className="skeleton-line w-80"></div>
                      <div className="skeleton-line w-40"></div>
                      <div className="skeleton-line w-70"></div>
                      <div className="skeleton-line w-50"></div>
                    </div>
                  </div>
                ) : ocrError ? (
                  <div className="ocr-error-state">
                    <div className="error-icon"><FaExclamationTriangle /></div>
                    <h3>Extraction Failed</h3>
                    <p>{ocrError}</p>
                    <p className="error-hint">Please try uploading a clearer image or enter the details manually.</p>
                  </div>
                ) : ocrResult && ocrResult.status === "error" ? (
                  <div className="ocr-error-state">
                    <div className="error-icon"><FaExclamationTriangle /></div>
                    <h3>Could Not Extract Information</h3>
                    <p>{ocrResult.message}</p>
                    <p className="error-hint">Please try again with a clearer image or enter manually.</p>
                  </div>
                ) : ocrResult && ocrResult.status === "no_medicine" ? (
                  <div className="ocr-error-state">
                    <div className="error-icon"><FaExclamationTriangle /></div>
                    <h3>No Medicine Detected</h3>
                    <p>{ocrResult.message}</p>
                    <p className="error-hint">Please try uploading a clear photo of a medicine strip, bottle, label or prescription, or enter the details manually.</p>
                  </div>
                ) : ocrResult ? (
                  <div className="ocr-result-container">
                    {/* Expiry red warning (medicine uploads) */}
                    {ocrResult.expiry?.status === "EXPIRED" && (
                      <div className="expiry-warning-banner">
                        <FaExclamationCircle /> <strong>Medicine Expired</strong>
                        <span>{ocrResult.expiry.message}</span>
                      </div>
                    )}
                    {ocrResult.expiry?.status === "EXPIRING_SOON" && (
                      <div className="expiry-warning-banner soon">
                        <FaExclamationTriangle /> <strong>Expiring Soon</strong>
                        <span>{ocrResult.expiry.message}</span>
                      </div>
                    )}
                    {/* Manual review banner */}
                    {ocrResult.needs_manual_review && (
                      <div className="manual-review-banner">
                        <FaExclamationTriangle /> <strong>Manual Review Required</strong>
                        <span>{ocrResult.message}</span>
                      </div>
                    )}
                    {/* Low confidence (moderate) banner */}
                    {ocrResult.status === "low_confidence" && !ocrResult.needs_manual_review && (
                      <div className="ocr-warning-banner"><FaExclamationTriangle /><span>{ocrResult.message}</span></div>
                    )}

                    {/* Image preview + confidence meter */}
                    <div className="result-summary-row">
                      {resultPreview && (
                        <div className="result-image-preview">
                          <img src={resultPreview} alt="Uploaded file preview" />
                          <span className="result-engine-badge">
                            {ocrResult.engine === "gemini" ? "AI Vision" : ocrResult.engine === "merged" ? "AI + OCR Merged" : "OCR Fallback"}
                          </span>
                        </div>
                      )}
                      <div className="result-overview">
                        <h3>{na(ocrResult.medicine_name)}</h3>
                        {ocrResult.disease && <p className="result-overview-disease"><FaDisease /> {na(ocrResult.disease)}</p>}
                        <ConfidenceMeter value={ocrResult.confidence} />
                        <div className="result-status-row">
                          <div className="result-status">
                            <span className="result-label">Status:</span>
                            {renderStatusBadge(ocrResult.status)}
                          </div>
                          <div className="result-status">
                            <span className="result-label">Confidence:</span>
                            {renderConfidenceBadge(ocrResult.confidence)}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Doctor card */}
                    {(ocrResult.doctor?.name || ocrResult.doctor?.registration_number || ocrResult.doctor?.hospital || ocrResult.doctor?.department) && (
                      <div className="result-doctor-card">
                        <div className="result-card-heading"><FaUserMd /> Doctor</div>
                        <div className="result-card-grid">
                          <div className="result-item"><span className="result-label"><FaUserMd /> Name</span><span className="result-value">{na(ocrResult.doctor.name)}</span></div>
                          <div className="result-item"><span className="result-label"><FaNotesMedical /> Registration No.</span><span className="result-value">{na(ocrResult.doctor.registration_number)}</span></div>
                          <div className="result-item"><span className="result-label"><FaHospital /> Hospital</span><span className="result-value">{na(ocrResult.doctor.hospital)}</span></div>
                          <div className="result-item"><span className="result-label"><FaStethoscope /> Department</span><span className="result-value">{na(ocrResult.doctor.department)}</span></div>
                        </div>
                      </div>
                    )}

                    {/* Disease / diagnosis card */}
                    {(ocrResult.disease || ocrResult.diagnosis || ocrResult.symptoms || ocrResult.doctor_notes) && (
                      <div className="result-disease-card">
                        <div className="result-card-heading"><FaDisease /> Disease & Diagnosis</div>
                        <div className="result-card-grid">
                          {ocrResult.disease && <div className="result-item"><span className="result-label"><FaDisease /> Disease</span><span className="result-value">{na(ocrResult.disease)}</span></div>}
                          {ocrResult.diagnosis && <div className="result-item"><span className="result-label"><FaNotesMedical /> Diagnosis</span><span className="result-value">{na(ocrResult.diagnosis)}</span></div>}
                          {ocrResult.symptoms && <div className="result-item"><span className="result-label"><FaExclamationTriangle /> Symptoms</span><span className="result-value">{na(ocrResult.symptoms)}</span></div>}
                          {ocrResult.doctor_notes && <div className="result-item"><span className="result-label"><FaNotesMedical /> Doctor Notes</span><span className="result-value">{na(ocrResult.doctor_notes)}</span></div>}
                        </div>
                      </div>
                    )}

                    {/* Patient card (prescription) */}
                    {ocrResult.patient?.name && (
                      <div className="result-patient-card">
                        <div className="result-card-heading"><FaUser /> Patient</div>
                        <div className="result-card-grid">
                          <div className="result-item"><span className="result-label"><FaUser /> Name</span><span className="result-value">{na(ocrResult.patient.name)}</span></div>
                          <div className="result-item"><span className="result-label"><FaCalendarAlt /> Age</span><span className="result-value">{na(ocrResult.patient.age)}</span></div>
                          <div className="result-item"><span className="result-label"><FaUserMd /> Gender</span><span className="result-value">{na(ocrResult.patient.gender)}</span></div>
                        </div>
                      </div>
                    )}

                    {/* Barcode / QR (medicine uploads) */}
                    {(ocrResult.barcode || ocrResult.qr_code) && (
                      <div className="result-code-row">
                        {ocrResult.barcode && <div className="result-code-chip"><FaBarcode /> Barcode: <strong>{ocrResult.barcode}</strong></div>}
                        {ocrResult.qr_code && <div className="result-code-chip"><FaQrcode /> QR: <strong>{ocrResult.qr_code}</strong></div>}
                      </div>
                    )}

                    {/* Medicine cards */}
                    {editableMedicines.length > 0 && (
                      <div className="result-medicine-cards">
                        <div className="result-card-heading"><FaPills /> Medicines Detected ({editableMedicines.length})</div>
                        {editableMedicines.map((m, idx) => (
                          <MedicineCard
                            key={`${m.medicine_name}-${idx}`}
                            medicine={m}
                            index={idx}
                            editing={editingIndex === idx}
                            onEdit={editingIndex === idx ? handleEditMedicine : () => { setEditingIndex(idx); }}
                            onDelete={handleDeleteMedicine}
                            onApply={applyOcrToForm}
                          />
                        ))}
                      </div>
                    )}

                    {/* Prescription details summary */}
                    {ocrResult.prescription_details && (
                      <div className="result-extra">
                        <div className="result-prescription-details">
                          <strong>Prescription Details:</strong>
                          <div className="prescription-summary">{ocrResult.prescription_details}</div>
                        </div>
                      </div>
                    )}

                    {/* Extracted JSON toggle */}
                    <div className="result-json-block">
                      <button className="ocr-btn secondary" onClick={() => setShowJson((s) => !s)}>
                        <FaCode /> {showJson ? "Hide" : "View"} Extracted JSON
                      </button>
                      {showJson && <pre className="result-json">{JSON.stringify(ocrResult, null, 2)}</pre>}
                    </div>

                    {/* Actions */}
                    <div className="result-actions">
                      <button
                        className="ocr-btn primary"
                        disabled={editableMedicines.length === 0}
                        onClick={() => applyOcrToForm(editableMedicines[0])}
                      ><FaArrowRight /> Apply to Entry Form</button>
                      <button className="ocr-btn secondary" onClick={() => { setOcrResult(null); setEditableMedicines([]); saveOCRState(null, []); }}><FaTimes /> Clear Results</button>
                    </div>
                  </div>
                ) : (
                  <div className="ocr-empty-state">
                    <div className="empty-icon"><FaCamera /></div>
                    <h3>No Results Yet</h3>
                    <p>Upload a medicine image or prescription above to extract information automatically.</p>
                    <div className="empty-tips">
                      <div className="tip-item"><FaCheckCircle className="tip-icon" /> Medicine Name & Dosage</div>
                      <div className="tip-item"><FaCheckCircle className="tip-icon" /> Brand, Strength & Quantity</div>
                      <div className="tip-item"><FaCheckCircle className="tip-icon" /> Doctor & Prescription Details</div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Card 5: Upload History */}
            <div className="ocr-card fade-in full-width">
              <div className="ocr-card-header">
                <div className="ocr-card-header-left">
                  <div className="ocr-card-icon history-icon"><FaHistory /></div>
                  <div><h2>Upload History</h2><p>View all your past uploads and extraction results</p></div>
                </div>
              </div>
              <div className="ocr-card-body">
                <div className="history-controls">
                  <div className="history-search">
                    <FaSearch />
                    <input type="text" placeholder="Search by file name..." value={historySearch} onChange={(e) => setHistorySearch(e.target.value)} />
                  </div>
                  <div className="history-filter">
                    <select value={historyFilter} onChange={(e) => setHistoryFilter(e.target.value)}>
                      <option value="All">All Status</option>
                      <option value="Completed">Completed</option>
                      <option value="Low Confidence">Low Confidence</option>
                    </select>
                  </div>
                </div>
                {filteredHistory.length === 0 ? (
                  <div className="history-empty">
                    <div className="empty-icon"><FaFileAlt /></div>
                    <h3>No Upload History</h3>
                    <p>Upload your first medicine image or prescription to see the history.</p>
                  </div>
                ) : (
                  <><div className="history-table-wrapper"><table className="history-table"><thead><tr>
                    <th>Preview</th><th>File Name</th><th>Upload Date</th><th>OCR Status</th><th>Medicine</th><th>Confidence</th><th>Action</th>
                  </tr></thead><tbody>
                    {paginatedHistory.map((item) => (
                      <tr key={item.id} className="history-row">
                        <td><div className={`history-file-type ${item.fileType === "application/pdf" ? "pdf" : "image"}`}>{item.fileType === "application/pdf" ? <FaFilePdf /> : <FaImage />}</div></td>
                        <td className="history-filename" title={item.fileName}>{item.fileName?.length > 30 ? item.fileName.slice(0,27)+"..." : item.fileName}</td>
                        <td className="history-date">{item.uploadDate}</td>
                        <td><span className={`history-status ${item.ocrStatus === "Completed" ? "success" : "warning"}`}>{item.ocrStatus}</span></td>
                        <td>{item.medicineName || "—"}</td>
                        <td><div className="history-confidence"><div className="confidence-bar-wrapper"><div className="confidence-bar-fill" style={{width: `${item.confidence||0}%`, background: item.confidence >= 90 ? "#22c55e" : item.confidence >= 70 ? "#eab308" : "#ef4444"}} /></div><span>{item.confidence||0}%</span></div></td>
                        <td><div className="history-actions">
                          <button className="history-action-btn view" title="View Details" onClick={() => alert(`Medicine: ${item.medicineName}\nDosage: ${item.dosage}\nConfidence: ${item.confidence}%`)}><FaEye /></button>
                          <button className="history-action-btn download" title="Download Result" onClick={() => downloadHistoryItem(item)}><FaDownload /></button>
                          <button className="history-action-btn delete" title="Delete" onClick={() => deleteHistoryItem(item.id)}><FaTrash /></button>
                        </div></td>
                      </tr>
                    ))}
                  </tbody></table></div>
                  <div className="history-pagination">
                    <span className="pagination-info">Showing {(currentPage-1)*itemsPerPage+1}–{Math.min(currentPage*itemsPerPage, filteredHistory.length)} of {filteredHistory.length}</span>
                    <div className="pagination-buttons">
                      <button className="page-btn" disabled={currentPage===1} onClick={() => setCurrentPage(p=>Math.max(1,p-1))}>Previous</button>
                      {Array.from({length: totalPages}, (_,i) => i+1).filter(p => p===1||p===totalPages||Math.abs(p-currentPage)<=1).map((p,idx,arr) => (<span key={p} style={{display:"inline-flex",alignItems:"center",gap:4}}>{idx>0&&arr[idx-1]!==p-1&&<span className="page-ellipsis">...</span>}<button className={`page-btn ${currentPage===p?"active":""}`} onClick={()=>setCurrentPage(p)}>{p}</button></span>))}
                      <button className="page-btn" disabled={currentPage===totalPages} onClick={() => setCurrentPage(p=>Math.min(totalPages,p+1))}>Next</button>
                    </div>
                  </div></>
                )}
              </div>
            </div>
          </div>
          <div className="ocr-footer">
            <p><FaInfoCircle /> AI Vision (Gemini) understands your image first. If confidence is below 85%, OCR runs as a fallback and both results are merged. Results may vary based on image quality — always verify extracted information.</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default PrescriptionOcr;
