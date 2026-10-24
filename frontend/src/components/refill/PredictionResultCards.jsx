import { FaBoxes, FaClock, FaCalendarAlt, FaFlask } from "react-icons/fa";

const formatNum = (n) => (Number.isInteger(n) ? `${n}` : n.toFixed(1));

function PredictionResultCards({ prediction }) {
  const cards = [
    {
      icon: <FaBoxes />,
      label: "Remaining Stock",
      value: `${prediction.remainingStock}`,
      unit: "Tablets Remaining",
      sub: prediction.hasManualStock
        ? "Based on manual stock update"
        : prediction.elapsedDays > 0
        ? `After ${prediction.elapsedDays} day${prediction.elapsedDays === 1 ? "" : "s"} of consumption`
        : "Full initial stock (no tracking data)",
      color: "teal",
    },
    {
      icon: <FaClock />,
      label: "Average Daily Consumption",
      value: formatNum(prediction.effectiveDaily),
      unit: "Tablets / Day",
      sub: prediction.consumptionFallback
        ? "No doses taken — using prescribed rate"
        : prediction.effectiveDaily !== prediction.nominalDaily
        ? `Effective: ${prediction.takenDoses} taken ÷ ${prediction.elapsedDays} days`
        : `${prediction.dosageFrequency} × ${prediction.qtyPerDose} per dose`,
      color: "blue",
    },
    {
      icon: <FaCalendarAlt />,
      label: "Estimated Stock Depletion Date",
      value: prediction.depletionDateLabel,
      unit: "",
      sub: `Stock lasts ${prediction.depletionDays} day${prediction.depletionDays === 1 ? "" : "s"} from today`,
      color: "orange",
    },
    {
      icon: <FaFlask />,
      label: "Recommended Refill Date",
      value: prediction.refillDateLabel,
      unit: "",
      sub: `${prediction.bufferDays} days before depletion`,
      color: "purple",
    },
  ];

  return (
    <div className="refill-result-grid">
      {cards.map((card) => (
        <div key={card.label} className="refill-result-card">
          <div className={`refill-result-icon refill-icon-${card.color}`}>{card.icon}</div>
          <div className="refill-result-label">{card.label}</div>
          <div className="refill-result-value">
            {card.value}
            {card.unit && <span className="refill-result-unit">{card.unit}</span>}
          </div>
          <div className="refill-result-sub">{card.sub}</div>
        </div>
      ))}
    </div>
  );
}

export default PredictionResultCards;
