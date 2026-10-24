import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  FaEnvelope,
  FaPhoneAlt,
  FaMapMarkerAlt,
  FaLinkedinIn,
  FaInstagram,
  FaTwitter,
  FaFacebookF,
  FaArrowUp,
} from "react-icons/fa";

import "../styles/Footer.css";

const QUICK_LINKS = [
  { label: "Home", to: "/" },
  { label: "Dashboard", to: "/dashboard" },
  { label: "Medicine", to: "/medicines" },
  { label: "Reminder", to: "/reminders" },
  { label: "AI Assistant", to: "/aiassistant" },
  { label: "About", to: "/", scrollToAbout: true },
];

// plain: true renders the label as static text (no Link / no navigation).
const RESOURCES = [
  { label: "About", plain: true },
  { label: "Blog", plain: true },
  { label: "Help Center", plain: true },
];

const LEGAL = [
  { label: "Privacy Policy", plain: true },
  { label: "Terms", plain: true },
  { label: "Disclaimer", plain: true },
];

// Future-ready: replace href="#" with the real profile URLs later.
const SOCIAL = [
  { icon: <FaLinkedinIn />, label: "LinkedIn" },
  { icon: <FaInstagram />, label: "Instagram" },
  { icon: <FaTwitter />, label: "Twitter (X)" },
  { icon: <FaFacebookF />, label: "Meta (Facebook)" },
];

function Footer() {
  const location = useLocation();
  const navigate = useNavigate();
  const [showBackToTop, setShowBackToTop] = useState(false);

  // Scrolls to the About section on the Home page. When the user is on
  // another page, navigate Home first and let the Home component finish
  // the scroll once it has rendered (via location.state.scrollToAbout).
  // Same behavior as the Navbar "About" link.
  const handleAboutClick = () => {
    if (location.pathname === "/") {
      document.getElementById("about")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    } else {
      navigate("/", { state: { scrollToAbout: true } });
    }
  };

  useEffect(() => {
    const onScroll = () => setShowBackToTop(window.scrollY > 300);
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const scrollToTop = () =>
    window.scrollTo({ top: 0, behavior: "smooth" });

  const renderLinks = (items) => (
    <ul className="footer-links">
      {items.map((item) => (
        <li key={item.label}>
          {item.plain ? (
            <span className="footer-link-text">{item.label}</span>
          ) : (
            <Link
              to={item.to}
              onClick={
                item.scrollToAbout
                  ? (e) => {
                      // Reuse the existing Home-page About scroll: prevent the
                      // Link's default navigation so the scrollToAbout state
                      // passed to "/" is not overridden.
                      e.preventDefault();
                      handleAboutClick();
                    }
                  : undefined
              }
            >
              {item.label}
            </Link>
          )}
        </li>
      ))}
    </ul>
  );

  return (
    <footer className="footer-section">
      <div className="footer-grid">
        {/* Brand */}
        <div className="footer-brand">
          <Link to="/" className="footer-logo" aria-label="PillSync Home">
            <span className="footer-logo-icon">💊</span>
            <span className="footer-logo-text">PillSync</span>
          </Link>
          <p className="footer-tagline">
            Intelligent medicine reminder and medication tracking platform.
          </p>
        </div>

        {/* Quick Links */}
        <div className="footer-col">
          <h3 className="footer-title">Quick Links</h3>
          {renderLinks(QUICK_LINKS)}
        </div>

        {/* Resources */}
        <div className="footer-col">
          <h3 className="footer-title">Resources</h3>
          {renderLinks(RESOURCES)}
        </div>

        {/* Legal */}
        <div className="footer-col">
          <h3 className="footer-title">Legal</h3>
          {renderLinks(LEGAL)}
        </div>

        {/* Contact Us */}
        <div className="footer-col">
          <h3 className="footer-title">Contact Us</h3>
          <ul className="footer-contact">
            <li>
              <a href="mailto:support@pillsync.com">
                <FaEnvelope />
                <span>support@pillsync.com</span>
              </a>
            </li>
            <li>
              <a href="tel:+911234567890">
                <FaPhoneAlt />
                <span>+91 12345 67890</span>
              </a>
            </li>
            <li>
              <span className="footer-contact-item">
                <FaMapMarkerAlt />
                <span>India</span>
              </span>
            </li>
          </ul>

          <div className="footer-social">
            {SOCIAL.map((social) => (
              <a
                key={social.label}
                href="#"
                className="footer-social-icon"
                aria-label={social.label}
                title={social.label}
              >
                {social.icon}
              </a>
            ))}
          </div>
        </div>
      </div>

      <div className="footer-bottom">
        <p>© 2026 PillSync. All Rights Reserved.</p>
      </div>

      <button
        type="button"
        className={`back-to-top${showBackToTop ? " visible" : ""}`}
        onClick={scrollToTop}
        aria-label="Back to top"
      >
        <FaArrowUp />
      </button>
    </footer>
  );
}

export default Footer;
