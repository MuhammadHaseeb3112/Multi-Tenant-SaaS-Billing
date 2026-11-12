import { useMemo, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../../context/AuthContext";
import { IconMenu } from "../../pages/dashboard/icons";
import BillingAlert from "./BillingAlert";
import Sidebar from "./Sidebar";
import { LayoutContext } from "./layoutContext";

import "./AppLayout.css";

// Shown in the small-screen top bar, next to the menu button.
const PAGE_TITLES: Record<string, string> = {
  "/subscriptions": "Subscriptions",
  "/invoices": "Invoices",
  "/usage": "Usage",
  "/analytics": "Analytics",
  "/team": "Team",
  "/notifications": "Notifications",
  "/audit": "Activity log",
  "/settings": "Settings",
};

/**
 * Shared shell for every signed-in page: the sidebar stays on the left
 * so users can jump between pages without going back to the dashboard.
 */
export default function AppLayout() {
  const { logout } = useAuth();
  const { pathname } = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const layout = useMemo(
    () => ({ openSidebar: () => setSidebarOpen(true) }),
    []
  );

  // The dashboard has its own top bar with a menu button.
  const showMenuButton = pathname !== "/dashboard";

  return (
    <LayoutContext.Provider value={layout}>
      <div className="app-shell">
        <Sidebar
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          onLogout={() => void logout()}
        />

        <div className={`app-shell-main ${showMenuButton ? "has-menu" : ""}`}>
          {showMenuButton && (
            <header className="app-shell-topbar">
              <button
                type="button"
                className="app-shell-menu"
                aria-label="Open menu"
                onClick={() => setSidebarOpen(true)}
              >
                <IconMenu />
              </button>

              <span className="app-shell-topbar-title">
                {PAGE_TITLES[pathname] ?? ""}
              </span>
            </header>
          )}

          <BillingAlert />

          {/* Keyed by path so each page change replays the entrance. */}
          <div key={pathname} className="app-route-progress" aria-hidden />

          <div key={`page-${pathname}`} className="app-page">
            <Outlet />
          </div>
        </div>
      </div>
    </LayoutContext.Provider>
  );
}
