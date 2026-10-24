import "../styles/Chart.css";

function HealthScore({ score = 0, loading = false, error = null, empty = false }) {
  const clamped = Math.max(0, Math.min(100, Math.round(score || 0)));

  const message =
    clamped >= 90
      ? "Your medication adherence is excellent."
      : clamped >= 75
      ? "Your medication adherence is good."
      : clamped >= 50
      ? "Your medication adherence needs improvement."
      : "Your medication adherence needs attention.";

  // Real states only — an API failure or a first load never masquerades as a
  // fake 0 score, and a brand-new user with no reminders isn't told their
  // adherence "needs attention".
  if (error) {
    return (
      <div className="healthCard">
        <h2>Health Score</h2>
        <div className="circle">
          <h1>—</h1>
          <span>unavailable</span>
        </div>
        <p>Couldn't load your health score.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="healthCard">
        <h2>Health Score</h2>
        <div className="circle">
          <h1>…</h1>
          <span>loading</span>
        </div>
        <p>Calculating from your medication data…</p>
      </div>
    );
  }

  if (empty) {
    return (
      <div className="healthCard">
        <h2>Health Score</h2>
        <div className="circle">
          <h1>—</h1>
          <span>no data</span>
        </div>
        <p>No adherence data yet — add a reminder and take your first dose to see your score.</p>
      </div>
    );
  }

  return (
    <div className="healthCard">

      <h2>Health Score</h2>

      <div className="circle">

        <h1>{clamped}</h1>

        <span>/100</span>

      </div>

      <p>{message}</p>

    </div>
  );
}

export default HealthScore;
