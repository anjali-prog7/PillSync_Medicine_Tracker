function CircularProgress({ percentage = 0, size = 120, strokeWidth = 8, color = "#0F766E", label = "" }) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percentage / 100) * circumference;

  return (
    <div className="circular-progress-wrapper" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="circular-progress-svg">
        {/* Background circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#e8edf2"
          strokeWidth={strokeWidth}
        />
        {/* Progress circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          className="circular-progress-arc"
          style={{
            transition: "stroke-dashoffset 1.5s ease-in-out",
          }}
        />
      </svg>
      <div className="circular-progress-center">
        <span className="circular-progress-value" style={{ color }}>
          {Math.round(percentage)}%
        </span>
        {label && <span className="circular-progress-label">{label}</span>}
      </div>
    </div>
  );
}

export default CircularProgress;
