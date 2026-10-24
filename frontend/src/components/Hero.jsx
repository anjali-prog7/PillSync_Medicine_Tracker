import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { GoogleLogin } from "@react-oauth/google";
import api from "../services/api";

function Hero() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const handleQuickLogin = async () => {
    if (!email || !password) {
      navigate("/login");
      return;
    }
    try {
      const response = await api.post("token/", {
        username: email,
        password: password,
      });
      localStorage.setItem("access", response.data.access);
      localStorage.setItem("refresh", response.data.refresh);
      navigate("/dashboard");
    } catch (error) {
      navigate("/login");
    }
  };

  return (
    <section className="hero">

      <div className="left">

        <h4>🛡️ Your Health, Our Priority</h4>

        <h1>
          Welcome to <br />
          <span>PillSync</span>
        </h1>

        <p>
          Your intelligent medicine reminder and medication tracking
          platform. Stay on track, never miss a dose, and take charge
          of your health.
        </p>

        <div className="features">

          <div className="feature">
            🔔
            <h3>Smart Reminders</h3>
            <p>Never miss a dose</p>
          </div>

          <div className="feature">
            📊
            <h3>Track & Analyze</h3>
            <p>Monitor your progress</p>
          </div>

          <div className="feature">
            🤖
            <h3>AI Assistant</h3>
            <p>Health Support 24/7</p>
          </div>

        </div>

      </div>

      <div className="right">

        <div className="login-card">

          <h2>Login to your account</h2>
          <p>Glad to see you again! 👋</p>

          <input
            type="text"
            placeholder="Username or email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />

          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          <div className="remember">
            <label className="remember-label">
              <input type="checkbox" />
              <span>Remember me</span>
            </label>
            <span className="forgot">Forgot password?</span>
          </div>

          <button className="login-btn" onClick={handleQuickLogin}>
            Login
          </button>

          <div className="divider">
            <span>or continue with</span>
          </div>

          <div className="social">
            <GoogleLogin
              onSuccess={(credentialResponse) => {
                console.log("Google Login Success");
                console.log(credentialResponse);
                navigate("/dashboard");
              }}
              onError={() => {
                console.log("Google Login Failed");
              }}
            />
          </div>

          <p className="signup">
            Don't have an account?{" "}
            <span onClick={() => navigate("/register")} style={{ cursor: "pointer" }}>
              Sign Up
            </span>
          </p>

        </div>

      </div>

    </section>
  );
}

export default Hero;