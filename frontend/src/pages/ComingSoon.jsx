import { Link } from "react-router-dom";
import { FaArrowLeft } from "react-icons/fa";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";

function ComingSoon({ title = "Coming Soon" }) {
  return (
    <>
      <Navbar />
      <main className="coming-soon-page">
        <div className="coming-soon-content">
          <div className="coming-soon-icon">🚧</div>
          <h1>{title}</h1>
          <p>
            This section is under development. Check back soon for updates!
          </p>
          <Link to="/" className="coming-soon-back">
            <FaArrowLeft /> Back to Home
          </Link>
        </div>
      </main>
      <Footer />
    </>
  );
}

export default ComingSoon;
