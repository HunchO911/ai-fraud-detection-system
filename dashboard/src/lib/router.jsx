/**
 * A tiny router built on the browser History API (five screens do not need a library).
 *   <Router>        provides the current path
 *   useRoute()      { path, navigate }
 *   <Link to="">    a real <a href> that navigates without reloading
 *   matchPath("/alerts/:id", "/alerts/42")  ->  { id: "42" } or null
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

const RouteContext = createContext(null);

export function matchPath(pattern, path) {
  const a = pattern.split("/").filter(Boolean);
  const b = path.split("/").filter(Boolean);
  if (a.length !== b.length) return null;
  const params = {};
  for (let i = 0; i < a.length; i++) {
    if (a[i].startsWith(":")) params[a[i].slice(1)] = decodeURIComponent(b[i]);
    else if (a[i] !== b[i]) return null;
  }
  return params;
}

export function Router({ children }) {
  const [path, setPath] = useState(window.location.pathname);

  useEffect(() => {
    const onPop = () => setPath(window.location.pathname);
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const navigate = useCallback((to, { replace = false } = {}) => {
    if (to === window.location.pathname + window.location.search) return;
    window.history[replace ? "replaceState" : "pushState"](null, "", to);
    setPath(window.location.pathname);
    window.scrollTo(0, 0);
  }, []);

  const value = useMemo(() => ({ path, navigate }), [path, navigate]);
  return <RouteContext.Provider value={value}>{children}</RouteContext.Provider>;
}

export const useRoute = () => useContext(RouteContext);

export function Link({ to, children, onClick, ...rest }) {
  const { navigate } = useRoute();
  const handle = (event) => {
    onClick?.(event);
    // Let the browser handle new-tab clicks (ctrl / cmd / middle button).
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey) return;
    event.preventDefault();
    navigate(to);
  };
  return (
    <a href={to} onClick={handle} {...rest}>
      {children}
    </a>
  );
}
