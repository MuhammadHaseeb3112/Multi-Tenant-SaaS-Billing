import type { ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { useUnreadNotifications } from "../../hooks/useUnreadNotifications";

import WorkspaceSwitcher from "../WorkspaceSwitcher";
import {
  IconActivity,
  IconBell,
  IconChart,
  IconCreditCard,
  IconDashboard,
  IconInvoice,
  IconLogout,
  IconSettings,
  IconUsers,
} from "../../pages/dashboard/icons";

interface NavItem {
  label: string;
  path: string;
  icon: ReactNode;
}

const MAIN_NAV: NavItem[] = [
  { label: "Dashboard", path: "/dashboard", icon: <IconDashboard /> },
  { label: "Subscriptions", path: "/subscriptions", icon: <IconCreditCard /> },
  { label: "Invoices", path: "/invoices", icon: <IconInvoice /> },
  { label: "Usage", path: "/usage", icon: <IconChart /> },
  { label: "Analytics", path: "/analytics", icon: <IconChart /> },
  { label: "Team", path: "/team", icon: <IconUsers /> },
];

const MANAGEMENT_NAV: NavItem[] = [
  { label: "Notifications", path: "/notifications", icon: <IconBell /> },
  { label: "Activity log", path: "/audit", icon: <IconActivity /> },
  { label: "Settings", path: "/settings", icon: <IconSettings /> },
];

interface SidebarProps {
  open: boolean;
  onClose: () => void;
  onLogout: () => void;
}

export default function Sidebar({ open, onClose, onLogout }: SidebarProps) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const unreadNotifications = useUnreadNotifications();

  const go = (path: string) => {
    onClose();
    navigate(path);
  };

  const renderItem = (item: NavItem) => (
    <button
      key={item.label}
      className={`nav-item ${pathname === item.path ? "active" : ""}`}
      type="button"
      onClick={() => go(item.path)}
    >
      {item.icon}
      <span>{item.label}</span>

      {item.path === "/notifications" &&
        unreadNotifications > 0 && (
          <span className="nav-badge">
            {unreadNotifications > 99 ? "99+" : unreadNotifications}
          </span>
        )}
    </button>
  );

  return (
    <>
      {open && <div className="mobile-overlay" onClick={onClose} />}

      <aside className={`sidebar ${open ? "open" : ""}`}>
        <div className="brand">
          <div className="brand-logo">S</div>

          <div>
            <div className="brand-name">SaaS Billing</div>
            <div className="brand-subtitle">Finance Platform</div>
          </div>
        </div>

        <div className="workspace">
          <WorkspaceSwitcher />
        </div>

        <div className="nav-title">Main menu</div>
        <nav className="nav-list">{MAIN_NAV.map(renderItem)}</nav>

        <div className="nav-title" style={{ marginTop: 25 }}>
          Management
        </div>
        <nav className="nav-list">{MANAGEMENT_NAV.map(renderItem)}</nav>

        <div className="sidebar-bottom">
          <div className="upgrade-card">
            <div className="upgrade-title">Need more power?</div>

            <div className="upgrade-text">
              Upgrade your plan to unlock higher usage limits and advanced
              billing features.
            </div>

            <button
              className="upgrade-button"
              type="button"
              onClick={() => go("/subscriptions")}
            >
              View plans
            </button>
          </div>

          <button className="nav-item" type="button" onClick={onLogout}>
            <IconLogout />
            <span>Sign out</span>
          </button>
        </div>
      </aside>
    </>
  );
}
