import { Link, useRoute } from "../lib/router.jsx";
import { useAuth } from "../lib/auth.jsx";

/** The frame around every signed-in page: brand, navigation, who you are, sign out. */
export default function Shell({ children }) {
  const { user, isStaff, isAdmin, logout } = useAuth();
  const { path } = useRoute();

  const links = [
    { to: "/", text: "Live", show: true, active: path === "/" },
    { to: "/alerts", text: "Alerts", show: isStaff, active: path.startsWith("/alerts") },
    { to: "/settings", text: "Settings", show: isAdmin, active: path === "/settings" },
  ].filter((l) => l.show);

  return (
    <>
      <header className="shell-header">
        <div className="shell-bar">
          <Link to="/" className="brand">
            <span className="brand-mark" aria-hidden="true"><i /></span>
            Fraud Watch
          </Link>
          <nav className="nav" aria-label="Main">
            {links.map((l) => (
              <Link key={l.to} to={l.to} aria-current={l.active ? "page" : undefined}>
                {l.text}
              </Link>
            ))}
          </nav>
          <div className="who">
            <span>
              <strong>{user.full_name || user.email}</strong> · {user.role}
            </span>
            <button className="btn btn-sm" onClick={logout}>Sign out</button>
          </div>
        </div>
      </header>
      <main className="page">{children}</main>
    </>
  );
}
