import { Navigate, Route, Routes } from "react-router-dom";
import Usage from "./pages/usage/Usage";

import Login from "./pages/auth/Login";
import Register from "./pages/auth/Register";
import Dashboard from "./pages/dashboard/Dashboard";
import Subscriptions from "./pages/subscriptions/Subscriptions";
import Analytics from "./pages/analytics/Analytics";
import Invoices from "./pages/invoices/Invoices";
import ProtectedRoute from "./routes/ProtectedRoute";
import Audit from "./pages/audit/Audit";
import Team from "./pages/team/Team";
import Notifications from "./pages/notifications/Notifications";
import Settings from "./pages/settings/Settings";

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />

      <Route path="/register" element={<Register />} />

      <Route
        path="/accept-invitation"
        element={<Register />}
      />

      <Route element={<ProtectedRoute />}>
        <Route path="/dashboard" element={<Dashboard />} />

        <Route
          path="/subscriptions"
          element={<Subscriptions />}
        />

        <Route
          path="/analytics"
          element={<Analytics />}
        />

        <Route
          path="/usage"
          element={<Usage />}
        />

        <Route
          path="/invoices"
          element={<Invoices />}
        />

        <Route
          path="/audit"
          element={<Audit />}
        />

        <Route
        path="/team"
        element={<Team />}
        />

        <Route
          path="/notifications"
          element={<Notifications />}
        />

        <Route
          path="/settings"
          element={<Settings />}
        />

      </Route>
      <Route
        path="*"
        element={<Navigate to="/dashboard" replace />}
      />
    </Routes>
  );
}

export default App;