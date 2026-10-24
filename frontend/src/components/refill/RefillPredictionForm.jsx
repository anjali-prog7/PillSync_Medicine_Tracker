import {
  FaCapsules,
  FaBoxes,
  FaClock,
  FaPills,
  FaCalendarTimes,
  FaCalendarDay,
  FaHourglassHalf,
  FaFlask,
  FaRobot,
  FaSpinner,
  FaSyncAlt,
  FaChevronDown,
} from "react-icons/fa";

const FIELDS = [
  {
    key: "medicineName",
    label: "Medicine Name",
    icon: <FaCapsules />,
    type: "text",
    placeholder: "e.g. Amlodipine 5mg",
    example: "Example: Amlodipine (BP medicine)",
    unit: "",
    full: true,
    required: true,
  },
  {
    key: "initialQty",
    label: "Initial Medicine Quantity",
    icon: <FaBoxes />,
    type: "number",
    min: "0",
    placeholder: "60",
    example: "Example: 60 Tablets",
    unit: "Tablets",
    required: true,
  },
  {
    key: "dosageFrequency",
    label: "Daily Dosage Frequency",
    icon: <FaClock />,
    type: "number",
    min: "0",
    placeholder: "2",
    example: "Example: 2",
    unit: "times / day",
    required: true,
  },
  {
    key: "qtyPerDose",
    label: "Quantity Consumed Per Dose",
    icon: <FaPills />,
    type: "number",
    min: "0",
    placeholder: "1",
    example: "Example: 1 Tablet",
    unit: "per dose",
    required: true,
  },
  {
    key: "missedDoses",
    label: "Missed Dosage History",
    icon: <FaCalendarTimes />,
    type: "number",
    min: "0",
    placeholder: "0",
    example: "Example: 3 Missed Doses",
    unit: "doses",
    required: false,
  },
  {
    key: "manualStock",
    label: "Manual Stock Updates",
    icon: <FaFlask />,
    type: "number",
    min: "0",
    placeholder: "Optional",
    example: "Current remaining stock",
    unit: "Tablets",
    required: false,
    optional: true,
  },
  {
    key: "trackingStartDate",
    label: "Tracking Start Date",
    icon: <FaCalendarDay />,
    type: "date",
    placeholder: "YYYY-MM-DD",
    example: "Start of this pack — used for consumption & adherence",
    unit: "",
    required: false,
    optional: true,
  },
  {
    key: "bufferDays",
    label: "Refill Buffer Days",
    icon: <FaHourglassHalf />,
    type: "select",
    options: [
      { value: "3", label: "3 Days" },
      { value: "5", label: "5 Days" },
      { value: "7", label: "7 Days" },
    ],
    example: "Refill this many days before depletion",
    unit: "",
    required: true,
  },
];

function RefillPredictionForm({ form, onChange, onPredict, predicting }) {
  const todayISO = (() => {
    const d = new Date();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${d.getFullYear()}-${mm}-${dd}`;
  })();

  return (
    <div className="refill-form-card">
      <div className="refill-card-header">
        <div className="refill-card-header-icon refill-icon-teal">
          <FaRobot />
        </div>
        <div>
          <h3>Refill Prediction</h3>
          <p>Enter your medication details to forecast refill needs</p>
        </div>
        <span className="refill-live-badge">
          <FaSyncAlt /> Auto-calculates
        </span>
      </div>

      <div className="refill-form-grid">
        {FIELDS.map((field) => (
          <div
            key={field.key}
            className={`refill-field${field.full ? " full" : ""}`}
          >
            <label htmlFor={`refill-${field.key}`}>
              <span className="refill-field-icon">{field.icon}</span>
              {field.label}
              {field.required && <span className="refill-required-star">*</span>}
              {field.optional && <span className="refill-optional">Optional</span>}
            </label>
            {field.type === "select" ? (
              <div className="refill-input-wrap">
                <select
                  id={`refill-${field.key}`}
                  className="refill-input refill-select"
                  value={form[field.key] ?? field.options[0].value}
                  onChange={(e) => onChange(field.key, e.target.value)}
                >
                  {field.options.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
                <FaChevronDown className="refill-select-chevron" />
              </div>
            ) : (
              <div className="refill-input-wrap">
                <input
                  id={`refill-${field.key}`}
                  type={field.type}
                  min={field.min}
                  max={field.type === "date" ? todayISO : undefined}
                  step={field.key === "medicineName" ? undefined : "any"}
                  className={`refill-input${field.unit ? " has-unit" : ""}`}
                  placeholder={field.placeholder}
                  value={form[field.key] ?? ""}
                  onChange={(e) => onChange(field.key, e.target.value)}
                />
                {field.unit && <span className="refill-input-unit">{field.unit}</span>}
              </div>
            )}
            {field.example && <span className="refill-field-example">{field.example}</span>}
          </div>
        ))}
      </div>

      <button
        className="refill-predict-btn"
        onClick={onPredict}
        disabled={predicting}
      >
        {predicting ? (
          <>
            <FaSpinner className="refill-spinner" /> Analyzing Stock…
          </>
        ) : (
          <>
            <FaRobot /> Predict Refill
          </>
        )}
      </button>

      <div className="refill-live-hint">
        <span className="refill-live-dot" />
        Live predictions update automatically as you type
      </div>
    </div>
  );
}

export default RefillPredictionForm;
