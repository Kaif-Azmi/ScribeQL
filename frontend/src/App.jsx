import { Navigate, Route, Routes } from "react-router-dom";
import ProtectedRoute from "./auth/ProtectedRoute.jsx";
import AccountPage from "./pages/AccountPage.jsx";
import LandingPage from "./pages/LandingPage.jsx";
import PrivacyPage from "./pages/PrivacyPage.jsx";
import ResetPasswordPage from "./pages/ResetPasswordPage.jsx";
import SignInPage from "./pages/SignInPage.jsx";
import SignUpPage from "./pages/SignUpPage.jsx";
import StartPage from "./pages/StartPage.jsx";
import StudioCustomPage from "./pages/StudioCustomPage.jsx";
import StudioDemoPage from "./pages/StudioDemoPage.jsx";
import VerifyPage from "./pages/VerifyPage.jsx";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/signin" element={<SignInPage />} />
      <Route path="/signup" element={<SignUpPage />} />
      <Route path="/verify" element={<VerifyPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/privacy" element={<PrivacyPage />} />
      <Route
        path="/start"
        element={
          <ProtectedRoute shell={false}>
            <StartPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/studio/demo"
        element={
          <ProtectedRoute shell={false}>
            <StudioDemoPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/studio/custom"
        element={
          <ProtectedRoute shell={false}>
            <StudioCustomPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/account"
        element={
          <ProtectedRoute>
            <AccountPage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
