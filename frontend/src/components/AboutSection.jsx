import {
  FaBell,
  FaChartLine,
  FaRobot,
  FaShieldAlt,
  FaUserMd,
  FaMobileAlt,
} from "react-icons/fa";

const FEATURES = [
  {
    icon: <FaBell />,
    title: "Smart Reminders",
    description:
      "Never miss a dose with intelligent, timed reminders via browser push notifications, email, and SMS alerts.",
  },
  {
    icon: <FaChartLine />,
    title: "Adherence Tracking",
    description:
      "Monitor your medication adherence with real-time analytics, progress charts, and health scores.",
  },
  {
    icon: <FaRobot />,
    title: "AI Health Assistant",
    description:
      "Get instant answers about your medications, drug interactions, and personalized health tips powered by AI.",
  },
  {
    icon: <FaShieldAlt />,
    title: "Data Privacy",
    description:
      "Your health data is encrypted and securely stored. We prioritize your privacy and data protection.",
  },
  {
    icon: <FaUserMd />,
    title: "Doctor Reports",
    description:
      "Generate comprehensive medication reports to share with your healthcare provider during visits.",
  },
  {
    icon: <FaMobileAlt />,
    title: "Easy Refills",
    description:
      "Track medicine quantities and get smart refill predictions so you never run out of essential medications.",
  },
];

function AboutSection() {
  return (
    <section className="about" id="about">
      <div className="about-container">
        <div className="about-header">
          <span className="about-badge">Why PillSync?</span>
          <h2>
            Everything You Need to Stay{" "}
            <span className="about-highlight">Healthy</span>
          </h2>
          <p className="about-subtitle">
            PillSync combines intelligent reminders, adherence tracking, and AI-powered
            health insights to help you take control of your medication regimen.
          </p>
        </div>

        <div className="about-grid">
          {FEATURES.map((feature, index) => (
            <div className="about-card" key={index}>
              <div className="about-card-icon">{feature.icon}</div>
              <h3>{feature.title}</h3>
              <p>{feature.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export default AboutSection;
