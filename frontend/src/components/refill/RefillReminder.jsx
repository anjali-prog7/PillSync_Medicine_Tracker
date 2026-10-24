import { FaBell, FaCalendarAlt } from "react-icons/fa";

function RefillReminder({ prediction }) {
  return (
    <div className="refill-msg-card">
      <div className="refill-msg-card-header">
        <div className="refill-msg-icon refill-icon-indigo">
          <FaBell />
        </div>
        <div>
          <h4>Refill Reminder</h4>
          <p>Automatically generated for your medication</p>
        </div>
      </div>
      <div className="refill-msg-text">{prediction.reminderMessage}</div>
      <div className="refill-msg-footer">
        <span className="refill-msg-chip">
          <FaCalendarAlt /> Refill before {prediction.refillDateLabel}
        </span>
      </div>
    </div>
  );
}

export default RefillReminder;
