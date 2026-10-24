import { FaUserFriends } from "react-icons/fa";

function CaregiverNotification({ prediction }) {
  return (
    <div className="refill-msg-card">
      <div className="refill-msg-card-header">
        <div className="refill-msg-icon refill-icon-rose">
          <FaUserFriends />
        </div>
        <div>
          <h4>Caregiver Notification</h4>
          <p>Alert prepared for family or caregiver</p>
        </div>
      </div>
      <div className="refill-msg-text refill-msg-text-alt">
        {prediction.caregiverMessage}
      </div>
      <div className="refill-msg-footer">
        <span className="refill-msg-chip refill-chip-green">Ready to send</span>
      </div>
    </div>
  );
}

export default CaregiverNotification;
