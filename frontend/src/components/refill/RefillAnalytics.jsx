import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import {
  FaBoxes,
  FaClock,
  FaCalendarCheck,
  FaCalendarTimes,
  FaHeartbeat,
  FaShieldAlt,
  FaChartLine,
  FaClipboardCheck,
} from "react-icons/fa";

const PROGRESS_COLORS = {
  green: "linear-gradient(90deg, #10B981, #34D399)",
  teal: "linear-gradient(90deg, #0F766E, #14B8A6)",
  orange: "linear-gradient(90deg, #F59E0B, #FBBF24)",
  rose: "linear-gradient(90deg, #F43F5E, #FB7185)",
  indigo: "linear-gradient(90deg, #6366F1, #818CF8)",
};

const ADHERENCE_STYLE = {
  Excellent: { color: "green", levelClass: "chip-green" },
  Good: { color: "teal", levelClass: "chip-teal" },
  Average: { color: "orange", levelClass: "chip-orange" },
  Poor: { color: "rose", levelClass: "chip-rose" },
};

const formatNum = (n) => (Number.isInteger(n) ? `${n}` : n.toFixed(1));

// Custom tooltip for the Stock Projection chart. Reads every value directly
// from the hovered row of the existing graph dataset (prediction.projected) —
// nothing is calculated here, and the graph logic is untouched.
function StockProjectionTooltip({ active, payload }) {
  if (!active || !payload || payload.length === 0) return null;

  const point = payload[0].payload; // { day, dayLabel, stock } from the dataset
  const isDepleted = point.stock <= 0;

  return (
    <div className="refill-chart-tooltip">
      <div className="refill-chart-tooltip-day">Day : {point.day}</div>
      <div className="refill-chart-tooltip-label">Remaining Stock</div>
      <div className="refill-chart-tooltip-value">{point.stock} Tablets</div>
      {isDepleted && (
        <div className="refill-chart-tooltip-badge">Stock Depleted</div>
      )}
    </div>
  );
}

function RefillAnalytics({ prediction }) {
  const stockHealthColor =
    prediction.stockHealth === "Healthy"
      ? "green"
      : prediction.stockHealth === "Warning"
      ? "orange"
      : "rose";

  const adherenceStyle =
    prediction.adherence !== null && prediction.adherence !== undefined
      ? ADHERENCE_STYLE[prediction.adherenceLevel] || ADHERENCE_STYLE.Good
      : null;

  const cards = [
    {
      icon: <FaBoxes />,
      label: "Remaining Stock",
      value: `${prediction.remainingStock}`,
      unit: "Tablets",
      color: "teal",
      sub: prediction.hasManualStock
        ? "Based on manual stock update"
        : prediction.elapsedDays > 0
        ? `Initial ${prediction.initialQty} − ${prediction.elapsedDays} days of consumption`
        : "Full initial stock (no tracking data yet)",
    },
    {
      icon: <FaClock />,
      label: "Average Daily Consumption",
      value: formatNum(prediction.effectiveDaily),
      unit: "Tablets / Day",
      color: "blue",
      sub: prediction.consumptionFallback
        ? "No doses taken — using prescribed rate"
        : prediction.effectiveDaily !== prediction.nominalDaily
        ? `${prediction.takenDoses} taken ÷ ${prediction.elapsedDays} tracking days`
        : `${prediction.dosageFrequency} × ${prediction.qtyPerDose} per dose`,
    },
    {
      icon: <FaCalendarCheck />,
      label: "Predicted Refill Date",
      value: prediction.refillDateLabel,
      unit: "",
      color: "orange",
      sub: `${prediction.bufferDays} days before depletion`,
    },
    {
      icon: <FaCalendarTimes />,
      label: "Missed Dosages",
      value: `${prediction.missedDoses}`,
      unit: "Doses",
      color: "rose",
      sub: prediction.missedDosesProvided
        ? prediction.hasTrackingDate
          ? "Included in adherence & consumption"
          : "Add a tracking start date for these to affect the prediction"
        : "None recorded",
    },
    {
      icon: <FaHeartbeat />,
      label: "Medicine Adherence",
      value: adherenceStyle ? `${prediction.adherence}%` : "N/A",
      unit: "",
      color: adherenceStyle ? adherenceStyle.color : "green",
      progress: adherenceStyle ? prediction.adherence : undefined,
      level: adherenceStyle ? prediction.adherenceLevel : null,
      levelClass: adherenceStyle ? adherenceStyle.levelClass : "",
      sub: adherenceStyle
        ? prediction.expectedDoses > 0
          ? `${prediction.takenDoses} of ${prediction.expectedDoses} expected doses taken`
          : "Tracking started today — no doses due yet"
        : "Add a tracking start date to compute adherence",
    },
    {
      icon: <FaShieldAlt />,
      label: "Stock Health",
      value: prediction.stockHealth,
      unit: "",
      color: stockHealthColor,
      sub:
        prediction.stockHealth === "Healthy"
          ? "More than 7 days of stock remaining"
          : prediction.stockHealth === "Warning"
          ? "7 or fewer days of stock remaining"
          : "3 or fewer days of stock remaining",
    },
    {
      icon: <FaChartLine />,
      label: "Prediction Confidence",
      value: `${prediction.confidence}%`,
      unit: "",
      color: "indigo",
      progress: prediction.confidence,
      sub: "Based on input completeness, stock data & tracking duration",
    },
  ];

  // Prediction Summary — display only. Every value is read directly from the
  // existing prediction engine output; nothing is recalculated here.
  const summaryItems = [
    { label: "Initial Stock", value: `${prediction.initialQty}`, unit: "Tablets" },
    { label: "Tracking Days", value: `${prediction.elapsedDays}`, unit: "Days" },
    { label: "Expected Consumption", value: `${prediction.expectedDoses}`, unit: "Tablets" },
    { label: "Missed Doses", value: `${prediction.missedDoses}` },
    { label: "Actual Consumption", value: `${prediction.takenDoses}`, unit: "Tablets" },
    { label: "Remaining Stock", value: `${prediction.remainingStock}`, unit: "Tablets" },
    { label: "Average Daily Consumption", value: formatNum(prediction.effectiveDaily), unit: "Tablets / Day" },
    { label: "Estimated Stock Depletion", value: prediction.depletionDateLabel },
    { label: "Recommended Refill Date", value: prediction.refillDateLabel },
  ];

  return (
    <section className="refill-analytics-section">
      <div className="refill-analytics-header">
        <div className="refill-analytics-title">
          <div className="refill-card-header-icon refill-icon-teal">
            <FaChartLine />
          </div>
          <div>
            <h3>Refill Analytics Dashboard</h3>
            <p>Live insights based on your current medication data</p>
          </div>
        </div>
      </div>

      <div className="refill-analytics-grid">
        {cards.map((card) => (
          <div key={card.label} className="refill-analytics-card">
            <div className="refill-analytics-top">
              <div className={`refill-analytics-icon refill-icon-${card.color}`}>
                {card.icon}
              </div>
              {card.progress !== undefined && (
                <span className="refill-analytics-big">{card.value}</span>
              )}
            </div>
            {card.progress === undefined && (
              <div className="refill-analytics-value">
                {card.value}
                {card.unit && <span className="refill-result-unit">{card.unit}</span>}
              </div>
            )}
            <div className="refill-analytics-label-row">
              <div className="refill-analytics-label">{card.label}</div>
              {card.level && (
                <span className={`refill-level-chip ${card.levelClass}`}>
                  {card.level}
                </span>
              )}
            </div>
            {card.progress !== undefined && (
              <div className="refill-progress">
                <div
                  className="refill-progress-fill"
                  style={{
                    width: `${card.progress}%`,
                    background: PROGRESS_COLORS[card.color] || PROGRESS_COLORS.teal,
                  }}
                />
              </div>
            )}
            {card.sub && <div className="refill-analytics-sub">{card.sub}</div>}
          </div>
        ))}
      </div>

      <div className="refill-summary-card">
        <div className="refill-chart-header">
          <div className="refill-chart-title">
            <FaClipboardCheck /> Prediction Summary
          </div>
          <span className="refill-chart-sub">
            Calculated from your current medicine data
          </span>
        </div>
        <div className="refill-summary-grid">
          {summaryItems.map((item) => (
            <div key={item.label} className="refill-summary-item">
              <div className="refill-summary-label">{item.label}</div>
              <div className="refill-summary-value">
                {item.value}
                {item.unit && (
                  <span className="refill-summary-unit">{item.unit}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="refill-chart-card">
        <div className="refill-chart-header">
          <div className="refill-chart-title">
            <FaChartLine /> Stock Projection
          </div>
          <span className="refill-chart-sub">
            Estimated tablets remaining over time
          </span>
        </div>
        <div className="refill-chart-body">
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={prediction.projected} margin={{ top: 10, right: 12, left: 0, bottom: 4 }}>
              <defs>
                <linearGradient id="refillStockGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#14B8A6" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="#14B8A6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
              <XAxis
                dataKey="dayLabel"
                tick={{ fontSize: 12, fill: "#94A3B8" }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 12, fill: "#94A3B8" }}
                axisLine={false}
                tickLine={false}
                width={40}
                allowDecimals={false}
              />
              <Tooltip
                content={<StockProjectionTooltip />}
                cursor={{ stroke: "#94A3B8", strokeDasharray: "4 4" }}
              />
              <Area
                type="monotone"
                dataKey="stock"
                stroke="#0F766E"
                strokeWidth={3}
                fill="url(#refillStockGradient)"
                name="Stock"
                activeDot={{ r: 5 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </section>
  );
}

export default RefillAnalytics;
