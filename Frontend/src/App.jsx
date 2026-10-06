import { Navigate, Route, Routes } from "react-router-dom";
import ProtectedRoute from "./routes/ProtectedRoute";
import DashboardLayout from "./layouts/DashboardLayout";
import AnalyticsPage from "./pages/dashboard/AnalyticsPage";
import ApiKeysPage from "./pages/dashboard/ApiKeysPage";
import OverviewPage from "./pages/dashboard/OverviewPage";
import PlaygroundPage from "./pages/dashboard/PlaygroundPage";
import ProvidersPage from "./pages/dashboard/ProvidersPage";
import LoginPage from "./pages/auth/LoginPage";
import RegisterPage from "./pages/auth/RegisterPage";

function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/dashboard" element={<DashboardLayout />}>
          <Route index element={<OverviewPage />} />
          <Route path="api-keys" element={<ApiKeysPage />} />
          <Route path="playground" element={<PlaygroundPage />} />
          <Route path="providers" element={<ProvidersPage />} />
          <Route path="analytics" element={<AnalyticsPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

export default App;
