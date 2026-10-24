import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import api from "../services/api";
import "../styles/Register.css";

// Indian mobile validation helper
const isValidIndianPhone = (phone) => {
  // Accept: 10 digits starting with 6-9, optional +91 or 0 prefix
  const cleaned = phone.replace(/[\s-]/g, "");
  return /^(?:\+91|0)?[6-9]\d{9}$/.test(cleaned);
};

const formatIndianPhone = (phone) => {
  // Strip +91 or 0 prefix, keep last 10 digits
  const cleaned = phone.replace(/[\s-]/g, "");
  if (cleaned.startsWith("+91")) return cleaned.slice(3);
  if (cleaned.startsWith("0")) return cleaned.slice(1);
  return cleaned;
};

function Register() {
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    username: "",
    email: "",
    phone: "",
    password: "",
    role: "PATIENT",
  });

  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [agreeTerms, setAgreeTerms] = useState(false);
  const [loading, setLoading] = useState(false);
  const [phoneError, setPhoneError] = useState("");

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!formData.username.trim()) {
      alert("Please enter your full name.");
      return;
    }

    if (!formData.email.trim()) {
      alert("Please enter your email address.");
      return;
    }

    // Validate Indian mobile number
    if (!formData.phone.trim()) {
      setPhoneError("Mobile Number is required.");
      alert("Please enter your mobile number.");
      return;
    }
    if (!isValidIndianPhone(formData.phone)) {
      setPhoneError("Enter a valid Indian mobile number (10 digits starting with 6-9, optional +91 or 0 prefix).");
      alert("Enter a valid Indian mobile number (10 digits starting with 6-9).");
      return;
    }
    setPhoneError("");

    if (!formData.password) {
      alert("Please create a password.");
      return;
    }

    if (formData.password !== confirmPassword) {
      alert("Password and Confirm Password do not match.");
      return;
    }

    if (!agreeTerms) {
      alert("Please agree to the Terms & Conditions and Privacy Policy.");
      return;
    }

    // Clear any stale tokens before registering
    localStorage.removeItem("access");
    localStorage.removeItem("refresh");

    console.log("Sending Data:", formData);

    try {
      setLoading(true);

      // Format phone to 10 digits before sending
      const payload = {
        ...formData,
        phone: formatIndianPhone(formData.phone),
      };

      const response = await api.post(
        "accounts/register/",
        payload
      );

      console.log("Success:", response.data);
      alert("Registration Successful!");
      navigate("/login");
    } catch (error) {
      console.log("===== ERROR START =====");
      console.log("Full Error:", error);
      console.log("Response:", error.response);
      console.log("Data:", error.response?.data);
      console.log("Status:", error.response?.status);
      console.log("===== ERROR END =====");

      // Handle "Network Error" gracefully with a user-friendly message
      if (!error.response) {
        alert(
          "Unable to connect to the server. Please make sure the backend is running and try again. (Network Error)"
        );
      } else {
        const errorData = error.response?.data;
        if (errorData && typeof errorData === "object") {
          // Format validation errors nicely
          const messages = Object.entries(errorData)
            .map(([field, errors]) => {
              const errs = Array.isArray(errors) ? errors.join(", ") : errors;
              return `${field}: ${errs}`;
            })
            .join("\n");
          alert(messages || "Registration failed. Please check your input.");
        } else {
          alert(
            JSON.stringify(errorData) ||
              "Registration failed. Please try again."
          );
        }
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Navbar />

      <main className="register-page">
        <div className="register-decoration decoration-one">+</div>
        <div className="register-decoration decoration-two">+</div>
        <div className="register-decoration decoration-three">+</div>

        <div className="register-dots dots-left">
          <span></span>
          <span></span>
          <span></span>
          <span></span>
          <span></span>
          <span></span>
          <span></span>
          <span></span>
          <span></span>
        </div>

        <div className="register-dots dots-right">
          <span></span>
          <span></span>
          <span></span>
          <span></span>
          <span></span>
          <span></span>
          <span></span>
          <span></span>
          <span></span>
        </div>

        <section className="register-card">
          <div className="register-logo">
            <svg
              viewBox="0 0 64 64"
              xmlns="http://www.w3.org/2000/svg"
              aria-hidden="true"
            >
              <g transform="rotate(-45 32 32)">
                <rect
                  x="17"
                  y="10"
                  width="30"
                  height="44"
                  rx="15"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="6"
                />
                <path
                  d="M17 32H47V39C47 47.3 40.3 54 32 54C23.7 54 17 47.3 17 39V32Z"
                  fill="currentColor"
                />
              </g>
            </svg>
          </div>

          <div className="register-heading">
            <h1>Create Your Account</h1>

            <p>
              Join <strong>PillSync</strong> and never miss your medicines again.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="register-form">
            <div className="register-field">
              <div className="field-icon">
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M12 12c2.76 0 5-2.24 5-5s-2.24-5-5-5-5 2.24-5 5 2.24 5 5 5Zm0 2c-4.42 0-8 2.24-8 5v2h16v-2c0-2.76-3.58-5-8-5Z" />
                </svg>
              </div>

              <div className="field-content">
                <label htmlFor="username">Full Name</label>

                <input
                  id="username"
                  type="text"
                  name="username"
                  value={formData.username}
                  onChange={handleChange}
                  placeholder="Enter your full name"
                  autoComplete="name"
                />
              </div>
            </div>

            <div className="register-field">
              <div className="field-icon">
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M20 4H4C2.9 4 2.01 4.9 2.01 6L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2Zm0 4-8 5-8-5V6l8 5 8-5v2Z" />
                </svg>
              </div>

              <div className="field-content">
                <label htmlFor="email">Email Address</label>

                <input
                  id="email"
                  type="email"
                  name="email"
                  value={formData.email}
                  onChange={handleChange}
                  placeholder="Enter your email address"
                  autoComplete="email"
                />
              </div>
            </div>

            <div className="register-field">
              <div className="field-icon">
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M6.62 10.79a15.46 15.46 0 0 0 6.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1C10.61 21 3 13.39 3 4c0-.55.45-1 1-1h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 1.02l-2.2 2.2Z" />
                </svg>
              </div>

              <div className="field-content">
                <label htmlFor="phone">
                  Mobile Number <span className="required-star">*</span>
                </label>

                <input
                  id="phone"
                  type="tel"
                  name="phone"
                  value={formData.phone}
                  onChange={(e) => {
                    setFormData({ ...formData, phone: e.target.value });
                    if (phoneError) setPhoneError("");
                  }}
                  placeholder="Enter your 10-digit mobile number"
                  autoComplete="tel"
                  className={phoneError ? "field-error" : ""}
                  maxLength={15}
                />
                {phoneError && (
                  <span className="field-error-message">{phoneError}</span>
                )}
              </div>
            </div>

            <div className="register-field">
              <div className="field-icon">
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M6.62 10.79a15.46 15.46 0 0 0 6.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1C10.61 21 3 13.39 3 4c0-.55.45-1 1-1h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 1.02l-2.2 2.2Z" />
                </svg>
              </div>

              <div className="field-content">
                <label htmlFor="role">Account Role</label>

                <select
                  id="role"
                  name="role"
                  value={formData.role}
                  onChange={handleChange}
                >
                  <option value="PATIENT">Patient</option>
                  <option value="CAREGIVER">Caregiver</option>
                </select>
              </div>
            </div>

            <div className="register-field">
              <div className="field-icon">
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2Zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2Zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1s3.1 1.39 3.1 3.1v2Z" />
                </svg>
              </div>

              <div className="field-content">
                <label htmlFor="password">Password</label>

                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  name="password"
                  value={formData.password}
                  onChange={handleChange}
                  placeholder="Create a strong password"
                  autoComplete="new-password"
                />
              </div>

              <button
                type="button"
                className="password-toggle"
                onClick={() => setShowPassword(!showPassword)}
                aria-label="Toggle password visibility"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5C21.27 7.61 17 4.5 12 4.5Zm0 12.5a5 5 0 1 1 0-10 5 5 0 0 1 0 10Zm0-8a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z" />
                </svg>
              </button>
            </div>

            <div className="register-field">
              <div className="field-icon">
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2Zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2Zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1s3.1 1.39 3.1 3.1v2Z" />
                </svg>
              </div>

              <div className="field-content">
                <label htmlFor="confirmPassword">
                  Confirm Password
                </label>

                <input
                  id="confirmPassword"
                  type={showConfirmPassword ? "text" : "password"}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Confirm your password"
                  autoComplete="new-password"
                />
              </div>

              <button
                type="button"
                className="password-toggle"
                onClick={() =>
                  setShowConfirmPassword(!showConfirmPassword)
                }
                aria-label="Toggle confirm password visibility"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5C21.27 7.61 17 4.5 12 4.5Zm0 12.5a5 5 0 1 1 0-10 5 5 0 0 1 0 10Zm0-8a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z" />
                </svg>
              </button>
            </div>

            <div className="terms-row">
              <input
                id="agreeTerms"
                type="checkbox"
                checked={agreeTerms}
                onChange={(e) => setAgreeTerms(e.target.checked)}
              />

              <label htmlFor="agreeTerms">
                I agree to the{" "}
                <span>Terms &amp; Conditions</span> and{" "}
                <span>Privacy Policy</span>
              </label>
            </div>

            <button
              type="submit"
              className="create-account-btn"
              disabled={loading}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M15 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4ZM6 10V7H4v3H1v2h3v3h2v-3h3v-2H6Zm9 4c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4Z" />
              </svg>

              {loading ? "Creating Account..." : "Create Account"}
            </button>
          </form>

          <div className="register-divider">
            <span></span>
            <p>OR</p>
            <span></span>
          </div>

         

          <p className="login-text">
            Already have an account?{" "}
            <Link to="/login">Login</Link>
          </p>
        </section>
      </main>

      <Footer />
    </>
  );
}

export default Register;