import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthProvider.jsx";
import AppShell from "../components/layout/AppShell.jsx";

export default function ProtectedRoute({ children, wide = false, shell = true }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    if (!shell) {
      return <p style={{ padding: "2rem", background: "#000", color: "#a1a1aa", minHeight: "100vh" }}>Loading…</p>;
    }
    return (
      <AppShell>
        <p>Loading…</p>
      </AppShell>
    );
  }

  if (!user) {
    const next = `${location.pathname}${location.search}`;
    return <Navigate to={`/signin?next=${encodeURIComponent(next)}`} replace />;
  }

  if (!shell) return children;
  return <AppShell wide={wide}>{children}</AppShell>;
}
