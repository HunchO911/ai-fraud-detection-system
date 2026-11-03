/** Who is signed in. Wrap the app in <AuthProvider>, read it with useAuth(). */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, clearTokens, getTokens, saveTokens, setSessionLostHandler } from "./api.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false); // false while we check a saved session

  // If a saved session exists, load the profile; a dead session just shows the login page.
  useEffect(() => {
    setSessionLostHandler(() => setUser(null));
    if (!getTokens()?.access) {
      setReady(true);
      return;
    }
    api
      .me()
      .then(setUser)
      .catch(() => {})
      .finally(() => setReady(true));
  }, []);

  const login = useCallback(async (email, password) => {
    const data = await api.login(email.trim(), password);
    saveTokens({ access: data.access, refresh: data.refresh });
    setUser(data.user);
    return data.user;
  }, []);

  const logout = useCallback(async () => {
    const refresh = getTokens()?.refresh;
    clearTokens();
    setUser(null);
    if (refresh) {
      try {
        await api.logout(refresh); // blacklist it on the server; ignore failures
      } catch {
        /* already signed out locally */
      }
    }
  }, []);

  const value = useMemo(
    () => ({
      user,
      ready,
      login,
      logout,
      isStaff: user?.role === "analyst" || user?.role === "admin",
      isAdmin: user?.role === "admin",
    }),
    [user, ready, login, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
