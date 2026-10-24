import Sidebar from "./Sidebar";
import Navbar from "./Navbar";

function Layout({ children }) {
  return (
    <div className="flex">
      <Sidebar />

      <div
        style={{
          marginLeft: "260px",
          width: "calc(100% - 260px)",
          background: "#F8FAFB",
          minHeight: "100vh",
        }}
      >
        <div style={{ padding: "35px" }}>
          <Navbar />
          {children}
        </div>
      </div>
    </div>
  );
}

export default Layout;