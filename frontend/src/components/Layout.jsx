import { Link, useLocation, useNavigate } from "react-router-dom";
import "./Layout.css";

function Layout({ children }) {
  const location = useLocation();
  const navigate = useNavigate();

  const isActive = (path) => location.pathname === path;

  const handleLogout = () => {
    navigate("/login");
  };

  return (
    <div className="layout">
      {/* ========== SIDEBAR ========== */}
      <aside className="sidebar">
        {/* Logo Section */}
        <div className="sidebar-header">
          <div className="logo">
            <div className="logo-icon">FG</div>
            <div>
              <h2>FraudGuard</h2>
              <p>AI Detection</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="sidebar-nav">
          <p className="nav-label">MAIN MENU</p>

          <Link to="/" className={`nav-item ${isActive("/") ? "active" : ""}`}>
            <span className="nav-icon">▣</span>
            <span>Dashboard</span>
          </Link>

          <Link
            to="/alerts"
            className={`nav-item ${isActive("/alerts") ? "active" : ""}`}
          >
            <span className="nav-icon">🔔</span>
            <span>Alerts</span>
          </Link>

          <Link
            to="/settings"
            className={`nav-item ${isActive("/settings") ? "active" : ""}`}
          >
            <span className="nav-icon">⚙</span>
            <span>Settings</span>
          </Link>
        </nav>

        {/* User + Logout */}
        <div className="sidebar-footer">
          <div className="user-card">
            <div className="user-avatar">FA</div>
            <div className="user-details">
              <p className="user-name">Fraud Analyst</p>
              <p className="user-role">Admin</p>
            </div>
          </div>

          <button className="logout-btn" onClick={handleLogout}>
            Sign Out
          </button>
        </div>
      </aside>

      {/* ========== MAIN CONTENT ========== */}
      <div className="main-content">
        <header className="navbar">
          <div className="navbar-left">
            <h3>
              {location.pathname === "/" && "Dashboard"}
              {location.pathname === "/alerts" && "Alerts"}
              {location.pathname.startsWith("/alerts/") && "Alert Details"}
              {location.pathname === "/settings" && "Settings"}
            </h3>
          </div>

          <div className="navbar-right">
            <div className="notification-bell">🔔</div>
            <div className="user-info">
              <span className="user-name">Fraud Analyst</span>
              <div className="avatar">FA</div>
            </div>
          </div>
        </header>

        <main className="page-content">{children}</main>
      </div>
    </div>
  );
}

export default Layout;