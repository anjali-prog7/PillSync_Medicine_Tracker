import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import api from "../services/api";
import "../styles/Login.css";

import { GoogleLogin } from "@react-oauth/google";
import axios from "axios";

function Login() {
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    username: "",
    password: "",
  });

  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };
  const handleSubmit = async (e) => {
  e.preventDefault();

  try {
    setLoading(true);

    console.log("LOGIN DATA:", formData);

    const response = await api.post("token/", formData);

    console.log("LOGIN RESPONSE:", response.data);

    localStorage.setItem("access", response.data.access);
    localStorage.setItem("refresh", response.data.refresh);

    alert("Login Successful!");

    navigate("/dashboard");
  } catch (error) {
    console.log("LOGIN ERROR:", error.response?.data);
    alert(JSON.stringify(error.response?.data));
  } finally {
    setLoading(false);
  }
};
 
  return (
    <>
      <Navbar />

      <main className="login-page">
        <div className="login-bg-circle circle-one"></div>
        <div className="login-bg-circle circle-two"></div>
        <div className="login-bg-circle circle-three"></div>

        <div className="login-dot-pattern pattern-top">
          {Array.from({ length: 24 }).map((_, index) => (
            <span key={index}></span>
          ))}
        </div>

        <div className="login-dot-pattern pattern-left">
          {Array.from({ length: 12 }).map((_, index) => (
            <span key={index}></span>
          ))}
        </div>

        <section className="login-container">
          <div className="login-welcome-panel">
            <div className="welcome-content">
              <div className="login-pill-logo">
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

              <h2>Welcome Back!</h2>

              <p>
                Login to continue your
                <span>PillSync</span>
                journey.
              </p>
            </div>

            <div className="medicine-illustration">
              <div className="leaf leaf-one"></div>
              <div className="leaf leaf-two"></div>
              <div className="leaf leaf-three"></div>

              <div className="medicine-bottle">
                <div className="bottle-cap"></div>

                <div className="bottle-body">
                  <div className="bottle-label">
                    <span className="medical-plus">+</span>
                  </div>
                </div>
              </div>

              <div className="pill-strip">
                <span></span>
                <span></span>
                <span></span>
                <span></span>
              </div>

              <div className="medicine-pill pill-one"></div>
              <div className="medicine-pill pill-two"></div>
            </div>
          </div>

          <div className="login-form-panel">
            <div className="login-heading">
              <h1>Login to your account</h1>

              <p>Glad to see you again! </p>
            </div>

            <form className="login-form" onSubmit={handleSubmit}>
              <div className="login-input-group">
                <label htmlFor="username">Username</label>

                <div className="login-input-wrapper">
                  <div className="login-input-icon">
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M12 12c2.76 0 5-2.24 5-5s-2.24-5-5-5-5 2.24-5 5 2.24 5 5 5Zm0 2c-4.42 0-8 2.24-8 5v2h16v-2c0-2.76-3.58-5-8-5Z" />
                    </svg>
                  </div>

                  <input
                    id="username"
                    type="text"
                    name="username"
                    value={formData.username}
                    onChange={handleChange}
                    placeholder="Enter your username"
                    autoComplete="username"
                    required
                  />
                </div>
              </div>

              <div className="login-input-group">
                <label htmlFor="password">Password</label>

                <div className="login-input-wrapper">
                  <div className="login-input-icon">
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2Zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2Zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1s3.1 1.39 3.1 3.1v2Z" />
                    </svg>
                  </div>

                  <input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    name="password"
                    value={formData.password}
                    onChange={handleChange}
                    placeholder="Enter your password"
                    autoComplete="current-password"
                    required
                  />

                  <button
                    type="button"
                    className="login-password-toggle"
                    onClick={() => setShowPassword(!showPassword)}
                    aria-label="Toggle password visibility"
                  >
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5C21.27 7.61 17 4.5 12 4.5Zm0 12.5a5 5 0 1 1 0-10 5 5 0 0 1 0 10Zm0-8a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z" />
                    </svg>
                  </button>
                </div>
              </div>

              <div className="login-options">
                <label className="remember-me">
                  <input
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                  />

                  <span>Remember me</span>
                </label>

                <button
                  type="button"
                  className="forgot-password"
                >
                  Forgot Password?
                </button>
              </div>

              <button
                type="submit"
                className="login-submit-btn"
                disabled={loading}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2Zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2Zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1s3.1 1.39 3.1 3.1v2Z" />
                </svg>

                {loading ? "Logging in..." : "Login"}
              </button>
            </form>

            <div className="login-divider">
              <span></span>
              <p>OR</p>
              <span></span>
            </div>

            <div className="login-social-buttons">

  <GoogleLogin
  onSuccess={(credentialResponse) => {
    console.log("Google Login Success");
    console.log(credentialResponse);

    localStorage.setItem(
      "google_token",
      credentialResponse.credential
    );

    alert("Google Login Successful!");

    navigate("/dashboard");
  }}
  onError={() => {
    alert("Google Login Failed");
  }}
/>

  <button type="button" className="login-social-btn">
    <span className="login-apple-icon">●</span>
    Continue with Apple
  </button>

</div>

            <p className="login-signup-text">
              Don't have an account?{" "}
              <Link to="/register">Sign Up</Link>
            </p>
          </div>
        </section>
      </main>

      <Footer />
    </>
  );
}

export default Login;