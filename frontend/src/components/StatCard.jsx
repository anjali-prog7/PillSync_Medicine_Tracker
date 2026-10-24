import "../styles/Card.css";

function StatCard({
  icon,
  title,
  value,
  subtitle
}) {

  return (

    <div className="card">

      <div className="cardIcon">
        {icon}
      </div>

      <div className="cardText">

        <h5>{title}</h5>

        <h2>{value}</h2>

        <p>{subtitle}</p>

      </div>

    </div>

  );

}

export default StatCard;