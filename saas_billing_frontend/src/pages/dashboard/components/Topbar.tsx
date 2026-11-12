import { useState } from "react";
import { useNavigate } from "react-router-dom";

import WorkspaceSwitcher from "../../../components/WorkspaceSwitcher";
import { useUnreadNotifications } from "../../../hooks/useUnreadNotifications";
import type { User } from "../../../types/auth";
import {
  IconBell,
  IconLogout,
  IconMenu,
  IconSearch,
  IconSettings,
} from "../icons";
import { initialsOf } from "../revenueChart";

interface TopbarProps {
  user: User | null;
  onOpenMenu: () => void;
  onLogout: () => void;
}

export default function Topbar({ user, onOpenMenu, onLogout }: TopbarProps) {
  const navigate = useNavigate();
  const [profileOpen, setProfileOpen] = useState(false);
  const unreadNotifications = useUnreadNotifications();

  const displayName = user?.first_name || user?.email || "there";

  return (
    <header className="topbar">
      <div className="topbar-left">
        <button
          className="icon-button mobile-menu"
          type="button"
          aria-label="Open menu"
          onClick={onOpenMenu}
        >
          <IconMenu />
        </button>

        <div className="page-title">Dashboard</div>

        <div className="breadcrumb">/ Overview</div>

        <WorkspaceSwitcher />
      </div>

      <div className="top-actions">
        <div className="search">
          <IconSearch />
          <input placeholder="Search..." />
        </div>

        <button
          className="icon-button"
          type="button"
          aria-label="Notifications"
          onClick={() => navigate("/notifications")}
        >
          <IconBell />
          {unreadNotifications > 0 && (
            <span className="notification-badge">
              {unreadNotifications > 99 ? "99+" : unreadNotifications}
            </span>
          )}
        </button>

        <div className="profile">
          <button
            className="profile-button"
            type="button"
            aria-expanded={profileOpen}
            onClick={() => setProfileOpen((value) => !value)}
          >
            <div className="avatar">{initialsOf(user)}</div>
            <span className="profile-name">{displayName}</span>
            <span style={{ color: "#64748b" }}>⌄</span>
          </button>

          {profileOpen && (
            <div className="profile-menu">
              <div className="profile-menu-header">
                <div className="profile-menu-name">{displayName}</div>

                <div className="profile-menu-email">
                  {user?.email || "Account"}
                </div>
              </div>

              <button
                className="menu-button"
                type="button"
                onClick={() => navigate("/settings")}
              >
                <IconSettings size={15} />
                Account settings
              </button>

              <button
                className="menu-button logout"
                type="button"
                onClick={onLogout}
              >
                <IconLogout size={15} />
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
