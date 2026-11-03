import { useEffect } from "react";
import { AuthProvider, useAuth } from "./lib/auth.jsx";
import { Router, matchPath, useRoute } from "./lib/router.jsx";
import Shell from "./components/Shell.jsx";
import { Empty, Loading } from "./components/States.jsx";
import Login from "./pages/Login.jsx";
import Live from "./pages/Live.jsx";
import Alerts from "./pages/Alerts.jsx";
import AlertDetail from "./pages/AlertDetail.jsx";
import Settings from "./pages/Settings.jsx";

function NoAccess({ text }) {
  return <Empty title="You don't have access to this page">{text}</Empty>;
}

/** Choose the page for the current address. Role checks here mirror the server's. */
function Screens() {
  const { path, navigate } = useRoute();
  const { user, ready, isStaff, isAdmin } = useAuth();

  // Signed out -> /login. Signed in on /login -> home.
  useEffect(() => {
    if (!ready) return;
    if (!user && path !== "/login") navigate("/login", { replace: true });
    if (user && path === "/login") navigate("/", { replace: true });
  }, [ready, user, path, navigate]);

  if (!ready) return <Loading text="Loading…" />;
  if (!user) return <Login />;

  let page;
  const detail = matchPath("/alerts/:id", path);
  if (path === "/") page = <Live />;
  else if (path === "/alerts") page = isStaff ? <Alerts /> : <NoAccess text="Alerts are for analysts and administrators." />;
  else if (detail) page = isStaff ? <AlertDetail id={detail.id} /> : <NoAccess text="Alerts are for analysts and administrators." />;
  else if (path === "/settings") page = isAdmin ? <Settings /> : <NoAccess text="Only administrators can change settings." />;
  else page = <Empty title="Page not found">Use the menu above to go back.</Empty>;

  return <Shell>{page}</Shell>;
}

export default function App() {
  return (
    <Router>
      <AuthProvider>
        <Screens />
      </AuthProvider>
    </Router>
  );
}
