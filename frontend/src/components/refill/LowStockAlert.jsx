import {
  FaExclamationTriangle,
  FaExclamationCircle,
  FaCheckCircle,
} from "react-icons/fa";

const ALERT_CONFIG = {
  Urgent: {
    icon: <FaExclamationCircle />,
    title: "Urgent — Stock Ends Tomorrow",
    text: "Critical. Your medicine stock will finish tomorrow. Arrange a refill now.",
  },
  Critical: {
    icon: <FaExclamationCircle />,
    title: "Critical Low Stock",
    text: "3 or fewer days of stock remain. Please refill immediately.",
  },
  Warning: {
    icon: <FaExclamationTriangle />,
    title: "Low Stock Warning",
    text: "7 or fewer days of stock remain. Plan a refill soon.",
  },
  Healthy: {
    icon: <FaCheckCircle />,
    title: "Stock Healthy",
    text: "Your current stock is sufficient for now.",
  },
};

function LowStockAlert({ prediction }) {
  const level = prediction.alertLevel || prediction.stockHealth || "Healthy";
  const config = ALERT_CONFIG[level] || ALERT_CONFIG.Healthy;
  const daysText =
    prediction.remainingStock <= 0
      ? "Empty today"
      : prediction.depletionDays <= 0
      ? "Finishes today"
      : `${prediction.depletionDays} day${prediction.depletionDays === 1 ? "" : "s"} left`;

  return (
    <div className={`refill-alert ${level.toLowerCase()}`}>
      <div className="refill-alert-icon">{config.icon}</div>
      <div className="refill-alert-content">
        <div className="refill-alert-title">{config.title}</div>
        <div className="refill-alert-text">{config.text}</div>
      </div>
      <span className="refill-alert-days">{daysText}</span>
    </div>
  );
}

export default LowStockAlert;
