import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { setOnUnauthorized } from "../api/client.js";
import { getMe, signOut as apiSignOut } from "../api/scribeql.js";
import { safeNext } from "../lib/safeNext.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [usage, setUsage] = useState(null);
  const [loading, setLoading] = useState(true);

  const refreshMe = useCallback(async () => {
    const result = await getMe();
    if (result.ok && result.data?.user) {
      setUser(result.data.user);
      setUsage(result.data.usage || null);
      return result.data;
    }
    setUser(null);
    setUsage(null);
    return null;
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await refreshMe();
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshMe]);

  useEffect(() => {
    setOnUnauthorized(({ next } = {}) => {
      setUser(null);
      setUsage(null);
      if (window.location.pathname === "/signin") return;
      const dest = safeNext(next, "/start");
      navigate(`/signin?next=${encodeURIComponent(dest)}`, { replace: true });
    });
    return () => setOnUnauthorized(null);
  }, [navigate]);

  const signOut = useCallback(async () => {
    await apiSignOut();
    setUser(null);
    setUsage(null);
    navigate("/", { replace: true });
  }, [navigate]);

  const value = useMemo(
    () => ({ user, usage, loading, setUser, setUsage, refreshMe, signOut }),
    [user, usage, loading, refreshMe, signOut]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
