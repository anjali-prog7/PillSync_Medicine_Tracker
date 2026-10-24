import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import "../styles/Navbar.css";

function Navbar() {

  const navigate = useNavigate();
  const location = useLocation();

  // Scrolls to the About section on the Home page. When the user is on
  // another page, navigate Home first and let the Home component finish
  // the scroll once it has rendered (via location.state.scrollToAbout).
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

  return (
    <nav className="navbar">

      {/* Logo */}
      <div 
        className="logo"
        onClick={() => navigate("/")}
      >
        💊 <span>PillSync</span>
      </div>


      {/* Menu */}
      <ul>

        <li onClick={() => navigate("/")}>
          Home
        </li>

        <li onClick={handleAboutClick}>
          About
        </li>

        <li onClick={() => navigate("/dashboard")}>
          Dashboard
        </li>

        <li onClick={() => navigate("/medicines")}>
          Medicine
        </li>

        <li onClick={() => navigate("/reminders")}>
          Reminder
        </li>

        <li onClick={() => navigate("/aiassistant")}>
          AI Assistant
        </li>

      </ul>


      {/* Signup Button */}
      <button
        className="signup-btn"
        onClick={() => navigate("/register")}
      >
        Sign Up
      </button>


    </nav>
  );
}

export default Navbar;