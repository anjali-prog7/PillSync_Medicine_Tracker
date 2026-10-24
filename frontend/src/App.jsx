import { useEffect } from "react";
import { Routes, Route, useLocation, useNavigate } from "react-router-dom";

import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import Profile from "./pages/Profile";
import NotFound from "./pages/NotFound";
import Medicines from "./pages/Medicines";
import Reminders from "./pages/Reminders";
import History from "./pages/History";
import AiAssistant from "./pages/AiAssistant";
import PrescriptionOcr from "./pages/PrescriptionOcr";
import Refill from "./pages/Refill";
import Report from "./pages/Report";
import ComingSoon from "./pages/ComingSoon";

import Navbar from "./components/Navbar";
import Hero from "./components/Hero";
import AboutSection from "./components/AboutSection";
import Footer from "./components/Footer";
import ProtectedRoute from "./components/ProtectedRoute";

import "./App.css";


function Home() {
  const location = useLocation();
  const navigate = useNavigate();

  // Support the Navbar "About" link: when arriving on Home with
  // { scrollToAbout: true }, smooth-scroll to the About section below
  // the main Hero content.
  useEffect(() => {
    if (location.state?.scrollToAbout) {
      document.getElementById("about")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
      navigate("/", { replace: true, state: null });
    }
  }, [location.state, navigate]);

  return (
    <>
      <Navbar />
      <Hero />
      <AboutSection />
      <Footer />
    </>
  );
}


function App() {

  return (

    <Routes>

      <Route path="/" element={<Home />} />

      <Route path="/login" element={<Login />} />

      <Route path="/register" element={<Register />} />


      {/* Protected Routes */}
      <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />

      <Route path="/medicines" element={<ProtectedRoute><Medicines /></ProtectedRoute>} />

      <Route path="/reminders" element={<ProtectedRoute><Reminders /></ProtectedRoute>} />

      <Route path="/history" element={<ProtectedRoute><History /></ProtectedRoute>} />

      <Route path="/profile" element={<ProtectedRoute><Profile /></ProtectedRoute>} />

      <Route path="/aiassistant" element={<ProtectedRoute><AiAssistant /></ProtectedRoute>} />

      <Route path="/dashboard/prescription-ocr" element={<ProtectedRoute><PrescriptionOcr /></ProtectedRoute>} />

      <Route path="/refill" element={<ProtectedRoute><Refill /></ProtectedRoute>} />

      <Route path="/report" element={<ProtectedRoute><Report /></ProtectedRoute>} />


      {/* Future pages — placeholder routing until implemented */}
      <Route path="/features" element={<ComingSoon title="Features" />} />
      <Route path="/about" element={<ComingSoon title="About" />} />
      <Route path="/blog" element={<ComingSoon title="Blog" />} />
      <Route path="/help" element={<ComingSoon title="Help Center" />} />
      <Route path="/privacy" element={<ComingSoon title="Privacy Policy" />} />
      <Route path="/terms" element={<ComingSoon title="Terms" />} />
      <Route path="/disclaimer" element={<ComingSoon title="Disclaimer" />} />

      <Route path="*"  element={<NotFound />} />


    </Routes>

  );
}


export default App;