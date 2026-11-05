import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { getUsageSummary } from "../../api/usage";
import type { UsageSummary } from "../../api/usage";
import { getSubscription } from "../../api/billing";
import type { Subscription } from "../../api/billing";
import { getAnalyticsOverview } from "../../api/analytics";
import type { AnalyticsOverview } from "../../api/analytics";
import { getInvoices } from "../../api/invoices";
import type { Invoice } from "../../api/invoices";
import { getAuditLogs } from "../../api/audit";
import type { AuditLog } from "../../api/audit";
import WorkspaceSwitcher from "../../components/WorkspaceSwitcher";
import { useOrganization } from "../../context/OrganizationContext";
import { useOrgRole } from "../../utils/roles";

type IconProps = {
  size?: number;
};

function IconDashboard({ size = 20 }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
    >
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
      <rect x="14" y="14" width="7" height="7" rx="1" />
    </svg>
  );
}

function IconCreditCard({ size = 20 }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
    >
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="M3 10h18" />
      <path d="M7 15h3" />
    </svg>
  );
}

function IconInvoice({ size = 20 }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
    >
      <path d="M6 3h9l3 3v15H6z" />
      <path d="M14 3v4h4" />
      <path d="M9 12h6" />
      <path d="M9 16h6" />
    </svg>
  );
}

function IconChart({ size = 20 }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
    >
      <path d="M4 19V5" />
      <path d="M4 19h16" />
      <path d="m7 15 4-4 3 2 5-7" />
    </svg>
  );
}

function IconUsers({ size = 20 }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
    >
      <circle cx="9" cy="8" r="3" />
      <path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6" />
      <path d="M16 5.5a3 3 0 0 1 0 5.8" />
      <path d="M18 14.5c1.8.8 3 2.6 3 4.5" />
    </svg>
  );
}

function IconBell({ size = 20 }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
    >
      <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" />
      <path d="M10 21h4" />
    </svg>
  );
}

function IconSettings({ size = 20 }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
    >
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-1.7 1.7-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5v.2h-2.4v-.2a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1L7 17l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H5.7v-2.4h.2a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.9L7 8.6l1.7-1.7.1.1a1.7 1.7 0 0 0 1.9.3 1.7 1.7 0 0 0 1-1.5v-.2h2.4v.2a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1 1.7 1.7-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.5 1h.2v2.4h-.2a1.7 1.7 0 0 0-1.5 1Z" />
    </svg>
  );
}

function IconLogout({ size = 20 }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
    >
      <path d="M10 17l5-5-5-5" />
      <path d="M15 12H3" />
      <path d="M21 4v16" />
    </svg>
  );
}


function IconArrowRight({ size = 16 }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
    >
      <path d="M5 12h14" />
      <path d="m13 6 6 6-6 6" />
    </svg>
  );
}

function IconMenu({ size = 22 }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
    >
      <path d="M4 6h16" />
      <path d="M4 12h16" />
      <path d="M4 18h16" />
    </svg>
  );
}

function IconSearch({ size = 19 }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
    >
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-4-4" />
    </svg>
  );
}

function IconPlus({ size = 18 }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
    >
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </svg>
  );
}

function Dashboard() {
  const { user, logout } = useAuth();
  const { activeOrganizationId } = useOrganization();
  const { isFinance } = useOrgRole();

  const navigate = useNavigate();

  const organizationId = activeOrganizationId;

  const [usage, setUsage] = useState<UsageSummary | null>(null);

  const [subscription, setSubscription] =
  useState<Subscription | null>(null);

  const [analytics, setAnalytics] =
  useState<AnalyticsOverview | null>(null);

  const [invoices, setInvoices] =
  useState<Invoice[]>([]);

  const [activity, setActivity] =
  useState<AuditLog[]>([]);

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);

  const displayName = user?.first_name || user?.email || "there";

  useEffect(() => {
    if (!organizationId) {
      return;
    }

    const loadUsage = async () => {
      try {
        const data = await getUsageSummary(organizationId);
        setUsage(data);
      } catch (error) {
        console.error("Failed to load dashboard usage:", error);
      }
    };

    void loadUsage();
  }, [organizationId]);

  useEffect(() => {
    if (!organizationId) {
      return;
    }

    const loadSubscription = async () => {
      try {
        const data = await getSubscription(organizationId);
        setSubscription(data);
      } catch (error) {
        console.error(
          "Failed to load dashboard subscription:",
          error,
        );
      }
    };

    void loadSubscription();
  }, [organizationId]);


  useEffect(() => {
    if (!organizationId) {
      return;
    }

    const loadAnalytics = async () => {
      try {
        const data = await getAnalyticsOverview(organizationId);
        setAnalytics(data);
      } catch (error) {
        console.error(
          "Failed to load dashboard analytics:",
          error,
        );
      }
    };

    void loadAnalytics();
  }, [organizationId]);


  useEffect(() => {
    if (!organizationId) {
      return;
    }

    const loadInvoices = async () => {
      try {
        const data = await getInvoices(organizationId);
        setInvoices(data);
      } catch (error) {
        console.error(
          "Failed to load dashboard invoices:",
          error,
        );
      }
    };

    void loadInvoices();
  }, [organizationId]);

  useEffect(() => {
    if (!organizationId) {
      return;
    }

    const loadActivity = async () => {
      try {
        const data = await getAuditLogs(organizationId);
        setActivity(data);
      } catch (error) {
        console.error(
          "Failed to load dashboard activity:",
          error,
        );
      }
    };

    void loadActivity();
  }, [organizationId]);


  const revenueChartData = useMemo(() => {
  const trend = analytics?.revenue_trend ?? [];

  const revenueMap = new Map(
    trend.map((item) => [
      item.month,
      Number.isFinite(Number(item.revenue))
        ? Number(item.revenue)
        : 0,
    ]),
  );

  const now = new Date();

  const months = Array.from({ length: 6 }, (_, index) => {
    const date = new Date(
      now.getFullYear(),
      now.getMonth() - (5 - index),
      1,
    );

    return {
      key: `${date.getFullYear()}-${String(
        date.getMonth() + 1,
      ).padStart(2, "0")}`,
      date,
    };
  });

  const data = months.map(({ key, date }) => ({
    month: key,
    revenue: revenueMap.get(key) ?? 0,
    label: date.toLocaleDateString("en-US", {
      month: "short",
    }),
  }));

  const chartLeft = 40;
  const chartRight = 745;
  const chartTop = 35;
  const chartBottom = 205;

  const maxRevenue = Math.max(
    ...data.map((item) => item.revenue),
    0,
  );

  const chartMax = maxRevenue > 0 ? maxRevenue : 1;

  return data.map((item, index) => {
    const x =
      data.length === 1
        ? (chartLeft + chartRight) / 2
        : chartLeft +
          (index / (data.length - 1)) *
            (chartRight - chartLeft);

    const y =
      chartBottom -
      (item.revenue / chartMax) *
        (chartBottom - chartTop);

    return {
      ...item,
      x,
      y,
    };
  });
}, [analytics]);

  const initials = useMemo(() => {
    if (user?.first_name) {
      return user.first_name.charAt(0).toUpperCase();
    }

    if (user?.email) {
      return user.email.charAt(0).toUpperCase();
    }

    return "U";
  }, [user]);

  const navItems = [
    {
      label: "Dashboard",
      icon: <IconDashboard />,
      active: true,
    },
    {
      label: "Subscriptions",
      icon: <IconCreditCard />,
    },
    {
      label: "Invoices",
      icon: <IconInvoice />,
    },
    {
      label: "Usage",
      icon: <IconChart />,
    },
    {
      label: "Analytics",
      icon: <IconChart />,
    },
    {
      label: "Team",
      icon: <IconUsers />,
    },
  ];

  return (
    <div className="saas-dashboard">
      <style>{`
        * {
          box-sizing: border-box;
        }

        .saas-dashboard {
          min-height: 100vh;
          width: 100%;
          background:
            radial-gradient(circle at 20% 0%, rgba(99, 102, 241, 0.10), transparent 28%),
            radial-gradient(circle at 90% 10%, rgba(139, 92, 246, 0.08), transparent 24%),
            #0a0b10;
          color: #f8fafc;
          display: flex;
          font-family:
            Inter,
            ui-sans-serif,
            system-ui,
            -apple-system,
            BlinkMacSystemFont,
            "Segoe UI",
            sans-serif;
          overflow-x: hidden;
        }

        .saas-dashboard::before {
          content: "";
          position: fixed;
          inset: 0;
          pointer-events: none;
          background-image:
            linear-gradient(rgba(255,255,255,0.018) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.018) 1px, transparent 1px);
          background-size: 48px 48px;
          mask-image: linear-gradient(to bottom, black, transparent 75%);
        }

        .sidebar {
          width: 250px;
          min-height: 100vh;
          background: rgba(15, 17, 24, 0.92);
          border-right: 1px solid rgba(148, 163, 184, 0.12);
          padding: 22px 14px;
          position: fixed;
          left: 0;
          top: 0;
          bottom: 0;
          z-index: 50;
          backdrop-filter: blur(18px);
          display: flex;
          flex-direction: column;
        }

        .brand {
          display: flex;
          align-items: center;
          gap: 11px;
          padding: 4px 10px 26px;
        }

        .brand-logo {
          width: 39px;
          height: 39px;
          border-radius: 11px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 21px;
          font-weight: 800;
          color: white;
          background: linear-gradient(135deg, #6366f1, #8b5cf6);
          box-shadow:
            0 8px 24px rgba(99, 102, 241, 0.28),
            inset 0 1px rgba(255,255,255,0.25);
        }

        .brand-name {
          font-size: 17px;
          font-weight: 750;
          letter-spacing: -0.3px;
        }

        .brand-subtitle {
          color: #64748b;
          font-size: 10px;
          margin-top: 2px;
          text-transform: uppercase;
          letter-spacing: 1px;
        }

        .workspace {
          margin: 0 5px 24px;
          padding: 12px;
          border-radius: 13px;
          background: rgba(255,255,255,0.035);
          border: 1px solid rgba(255,255,255,0.07);
        }

        .workspace-label {
          color: #64748b;
          font-size: 10px;
          text-transform: uppercase;
          letter-spacing: 1px;
          margin-bottom: 8px;
        }

        .workspace-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
        }

        .workspace-info {
          min-width: 0;
        }

        .workspace-name {
          font-size: 13px;
          font-weight: 650;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .workspace-plan {
          font-size: 11px;
          color: #818cf8;
          margin-top: 3px;
        }

        .workspace-arrow {
          color: #64748b;
        }

        .nav-title {
          padding: 0 11px 9px;
          color: #475569;
          font-size: 10px;
          text-transform: uppercase;
          letter-spacing: 1.2px;
          font-weight: 700;
        }

        .nav-list {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .nav-item {
          width: 100%;
          border: 0;
          background: transparent;
          color: #94a3b8;
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 11px 12px;
          border-radius: 10px;
          font-size: 13px;
          font-weight: 550;
          cursor: pointer;
          text-align: left;
          transition: all 0.2s ease;
        }

        .nav-item:hover {
          background: rgba(255,255,255,0.045);
          color: #f8fafc;
          transform: translateX(2px);
        }

        .nav-item.active {
          background: linear-gradient(
            90deg,
            rgba(99,102,241,0.18),
            rgba(99,102,241,0.06)
          );
          color: #c7d2fe;
          box-shadow: inset 2px 0 #6366f1;
        }

        .nav-item.active svg {
          color: #818cf8;
        }

        .sidebar-bottom {
          margin-top: auto;
        }

        .upgrade-card {
          padding: 15px;
          margin: 10px 4px 14px;
          border-radius: 14px;
          background:
            radial-gradient(circle at top right, rgba(139,92,246,0.28), transparent 55%),
            rgba(99,102,241,0.10);
          border: 1px solid rgba(129,140,248,0.18);
        }

        .upgrade-title {
          font-size: 13px;
          font-weight: 700;
        }

        .upgrade-text {
          color: #94a3b8;
          font-size: 11px;
          line-height: 1.5;
          margin: 5px 0 12px;
        }

        .upgrade-button {
          width: 100%;
          border: 0;
          border-radius: 8px;
          padding: 8px;
          color: white;
          background: linear-gradient(135deg, #6366f1, #7c3aed);
          font-weight: 650;
          font-size: 11px;
          cursor: pointer;
          transition: transform 0.2s ease, box-shadow 0.2s ease;
        }

        .upgrade-button:hover {
          transform: translateY(-1px);
          box-shadow: 0 8px 20px rgba(99,102,241,0.25);
        }

        .main {
          width: calc(100% - 250px);
          margin-left: 250px;
          min-height: 100vh;
        }

        .topbar {
          height: 72px;
          padding: 0 30px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          border-bottom: 1px solid rgba(148,163,184,0.10);
          background: rgba(10,11,16,0.72);
          backdrop-filter: blur(16px);
          position: sticky;
          top: 0;
          z-index: 30;
        }

        .topbar-left {
          display: flex;
          align-items: center;
          gap: 15px;
        }

        .page-title {
          font-size: 15px;
          font-weight: 650;
          color: #e2e8f0;
        }

        .breadcrumb {
          color: #475569;
          font-size: 12px;
        }

        .search {
          width: 245px;
          height: 38px;
          display: flex;
          align-items: center;
          gap: 9px;
          padding: 0 12px;
          border: 1px solid rgba(148,163,184,0.13);
          border-radius: 9px;
          background: rgba(255,255,255,0.025);
          color: #64748b;
        }

        .search input {
          width: 100%;
          border: 0;
          outline: none;
          color: #cbd5e1;
          background: transparent;
          font-size: 12px;
        }

        .search input::placeholder {
          color: #475569;
        }

        .top-actions {
          display: flex;
          align-items: center;
          gap: 9px;
        }

        .icon-button {
          width: 38px;
          height: 38px;
          border-radius: 9px;
          border: 1px solid rgba(148,163,184,0.12);
          background: rgba(255,255,255,0.025);
          color: #94a3b8;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          position: relative;
          transition: all 0.2s ease;
        }

        .icon-button:hover {
          color: #f8fafc;
          background: rgba(255,255,255,0.06);
        }

        .notification-dot {
          position: absolute;
          top: 8px;
          right: 8px;
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background: #818cf8;
          box-shadow: 0 0 0 3px rgba(129,140,248,0.12);
        }

        .profile {
          position: relative;
        }

        .profile-button {
          display: flex;
          align-items: center;
          gap: 9px;
          padding: 4px 7px 4px 4px;
          border: 1px solid rgba(148,163,184,0.12);
          border-radius: 10px;
          background: rgba(255,255,255,0.025);
          color: #e2e8f0;
          cursor: pointer;
        }

        .avatar {
          width: 30px;
          height: 30px;
          border-radius: 8px;
          background: linear-gradient(135deg, #6366f1, #8b5cf6);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 12px;
          font-weight: 750;
        }

        .profile-name {
          font-size: 11px;
          font-weight: 650;
          max-width: 105px;
          overflow: hidden;
          white-space: nowrap;
          text-overflow: ellipsis;
        }

        .profile-menu {
          position: absolute;
          right: 0;
          top: 47px;
          width: 180px;
          padding: 7px;
          border-radius: 12px;
          background: #171923;
          border: 1px solid rgba(148,163,184,0.15);
          box-shadow: 0 18px 50px rgba(0,0,0,0.35);
          animation: dropdown 0.16s ease-out;
          z-index: 100;
        }

        @keyframes dropdown {
          from {
            opacity: 0;
            transform: translateY(-5px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        .profile-menu-header {
          padding: 9px;
          border-bottom: 1px solid rgba(148,163,184,0.09);
          margin-bottom: 5px;
        }

        .profile-menu-name {
          font-size: 12px;
          font-weight: 650;
        }

        .profile-menu-email {
          color: #64748b;
          font-size: 10px;
          margin-top: 3px;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .menu-button {
          width: 100%;
          border: 0;
          background: transparent;
          color: #94a3b8;
          padding: 9px;
          border-radius: 7px;
          display: flex;
          align-items: center;
          gap: 9px;
          cursor: pointer;
          font-size: 11px;
          text-align: left;
        }

        .menu-button:hover {
          color: #f8fafc;
          background: rgba(255,255,255,0.05);
        }

        .menu-button.logout {
          color: #f87171;
        }

        .content {
          padding: 30px;
          max-width: 1600px;
          margin: 0 auto;
        }

        .hero {
          display: flex;
          justify-content: space-between;
          align-items: flex-end;
          gap: 20px;
          margin-bottom: 26px;
          animation: fadeUp 0.45s ease both;
        }

        @keyframes fadeUp {
          from {
            opacity: 0;
            transform: translateY(12px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        .hero-eyebrow {
          color: #818cf8;
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 1px;
          text-transform: uppercase;
          margin-bottom: 7px;
        }

        .hero h1 {
          margin: 0;
          font-size: clamp(25px, 3vw, 34px);
          letter-spacing: -1.2px;
          line-height: 1.1;
        }

        .hero p {
          color: #64748b;
          margin: 9px 0 0;
          font-size: 13px;
        }

        .primary-button {
          border: 0;
          height: 40px;
          padding: 0 15px;
          border-radius: 9px;
          color: white;
          background: linear-gradient(135deg, #6366f1, #7c3aed);
          font-weight: 650;
          font-size: 12px;
          display: flex;
          align-items: center;
          gap: 7px;
          cursor: pointer;
          box-shadow: 0 8px 25px rgba(99,102,241,0.20);
          transition: all 0.2s ease;
        }

        .primary-button:hover {
          transform: translateY(-2px);
          box-shadow: 0 12px 30px rgba(99,102,241,0.30);
        }

        .stats-grid {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 15px;
          margin-bottom: 18px;
        }

        .stat-card {
          min-height: 143px;
          padding: 19px;
          border-radius: 15px;
          border: 1px solid rgba(148,163,184,0.11);
          background:
            linear-gradient(
              145deg,
              rgba(255,255,255,0.045),
              rgba(255,255,255,0.018)
            );
          box-shadow: 0 12px 35px rgba(0,0,0,0.12);
          animation: fadeUp 0.45s ease both;
          transition:
            transform 0.22s ease,
            border-color 0.22s ease,
            background 0.22s ease;
        }

        .stat-card:nth-child(2) {
          animation-delay: 0.06s;
        }

        .stat-card:nth-child(3) {
          animation-delay: 0.12s;
        }

        .stat-card:nth-child(4) {
          animation-delay: 0.18s;
        }

        .stat-card:hover {
          transform: translateY(-3px);
          border-color: rgba(129,140,248,0.20);
          background:
            linear-gradient(
              145deg,
              rgba(255,255,255,0.06),
              rgba(255,255,255,0.022)
            );
        }

        .stat-top {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .stat-label {
          color: #64748b;
          font-size: 11px;
          font-weight: 600;
        }

        .stat-icon {
          width: 32px;
          height: 32px;
          border-radius: 9px;
          display: flex;
          align-items: center;
          justify-content: center;
          color: #a5b4fc;
          background: rgba(99,102,241,0.10);
          border: 1px solid rgba(129,140,248,0.12);
        }

        .stat-value {
          font-size: 25px;
          font-weight: 750;
          letter-spacing: -0.8px;
          margin-top: 15px;
        }

        .stat-bottom {
          display: flex;
          align-items: center;
          gap: 5px;
          margin-top: 8px;
          font-size: 10px;
          color: #64748b;
        }

        .positive {
          color: #34d399;
          display: flex;
          align-items: center;
          gap: 1px;
          font-weight: 650;
        }

        .neutral {
          color: #818cf8;
          font-weight: 600;
        }

        .main-grid {
          display: grid;
          grid-template-columns: minmax(0, 1.55fr) minmax(320px, 0.85fr);
          gap: 18px;
          margin-bottom: 18px;
        }

        .panel {
          border: 1px solid rgba(148,163,184,0.11);
          background: rgba(17,19,27,0.75);
          border-radius: 15px;
          overflow: hidden;
          box-shadow: 0 12px 35px rgba(0,0,0,0.10);
          animation: fadeUp 0.55s ease both;
        }

        .panel-header {
          padding: 18px 19px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          border-bottom: 1px solid rgba(148,163,184,0.08);
        }

        .panel-title {
          font-size: 13px;
          font-weight: 700;
        }

        .panel-subtitle {
          color: #64748b;
          font-size: 10px;
          margin-top: 4px;
        }

        .period-select {
          color: #94a3b8;
          background: rgba(255,255,255,0.035);
          border: 1px solid rgba(148,163,184,0.10);
          border-radius: 7px;
          padding: 7px 9px;
          outline: none;
          font-size: 10px;
        }

        .chart-container {
          height: 285px;
          padding: 18px 19px 15px;
          position: relative;
        }

        .chart-svg {
          width: 100%;
          height: 100%;
          overflow: visible;
        }

        .chart-line {
          stroke-dasharray: 700;
          stroke-dashoffset: 700;
          animation: drawChart 1.5s ease forwards;
        }

        @keyframes drawChart {
          to {
            stroke-dashoffset: 0;
          }
        }

        .chart-area {
          opacity: 0;
          animation: chartArea 1s ease 0.35s forwards;
        }

        @keyframes chartArea {
          to {
            opacity: 1;
          }
        }

        .chart-grid-line {
          stroke: rgba(148,163,184,0.07);
          stroke-width: 1;
        }

        .chart-label {
          fill: #475569;
          font-size: 9px;
        }

        .chart-point {
          fill: #11131b;
          stroke: #818cf8;
          stroke-width: 2;
          opacity: 0;
          animation: pointIn 0.3s ease forwards;
        }

        @keyframes pointIn {
          to {
            opacity: 1;
          }
        }

        .subscription-body {
          padding: 20px;
        }

        .subscription-plan {
          display: flex;
          align-items: center;
          gap: 13px;
          margin-bottom: 22px;
        }

        .plan-icon {
          width: 48px;
          height: 48px;
          border-radius: 13px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: 800;
          background: linear-gradient(135deg, #6366f1, #8b5cf6);
          box-shadow: 0 10px 25px rgba(99,102,241,0.18);
        }

        .plan-name {
          font-size: 18px;
          font-weight: 750;
        }

        .plan-description {
          color: #64748b;
          font-size: 10px;
          margin-top: 3px;
        }

        .status-pill {
          margin-left: auto;
          padding: 5px 8px;
          border-radius: 20px;
          font-size: 9px;
          color: #34d399;
          background: rgba(52,211,153,0.08);
          border: 1px solid rgba(52,211,153,0.14);
          font-weight: 700;
        }

        .subscription-info {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px;
        }

        .info-box {
          padding: 12px;
          border-radius: 10px;
          background: rgba(255,255,255,0.025);
          border: 1px solid rgba(148,163,184,0.07);
        }

        .info-label {
          color: #64748b;
          font-size: 9px;
          text-transform: uppercase;
          letter-spacing: 0.7px;
        }

        .info-value {
          font-size: 12px;
          font-weight: 650;
          margin-top: 5px;
          color: #cbd5e1;
        }

        .usage-section {
          margin-top: 22px;
        }

        .usage-header {
          display: flex;
          justify-content: space-between;
          margin-bottom: 9px;
        }

        .usage-title {
          font-size: 10px;
          color: #94a3b8;
        }

        .usage-number {
          font-size: 10px;
          color: #cbd5e1;
          font-weight: 650;
        }

        .progress {
          height: 7px;
          border-radius: 99px;
          overflow: hidden;
          background: rgba(255,255,255,0.06);
        }

        .progress-fill {
          height: 100%;
          width: 0;
          border-radius: inherit;
          background: linear-gradient(90deg, #6366f1, #a78bfa);
          box-shadow: 0 0 16px rgba(99,102,241,0.30);
          transition: width 0.4s ease;
        }

        .usage-footer {
          display: flex;
          justify-content: space-between;
          color: #475569;
          font-size: 9px;
          margin-top: 7px;
        }

        .lower-grid {
          display: grid;
          grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr);
          gap: 18px;
        }

        .invoice-list {
          padding: 4px 19px 8px;
        }

        .invoice-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          padding: 14px 0;
          border-bottom: 1px solid rgba(148,163,184,0.07);
        }

        .invoice-row:last-child {
          border-bottom: 0;
        }

        .invoice-left {
          display: flex;
          align-items: center;
          gap: 11px;
          min-width: 0;
        }

        .invoice-icon {
          width: 35px;
          height: 35px;
          flex-shrink: 0;
          border-radius: 9px;
          display: flex;
          align-items: center;
          justify-content: center;
          color: #818cf8;
          background: rgba(99,102,241,0.08);
        }

        .invoice-number {
          font-size: 11px;
          font-weight: 650;
        }

        .invoice-date {
          color: #475569;
          font-size: 9px;
          margin-top: 3px;
        }

        .invoice-right {
          text-align: right;
          flex-shrink: 0;
        }

        .invoice-amount {
          font-size: 11px;
          font-weight: 700;
        }

        .paid {
          color: #34d399;
          font-size: 9px;
          margin-top: 3px;
        }

        .activity-list {
          padding: 8px 19px 12px;
        }

        .activity-item {
          display: flex;
          gap: 11px;
          padding: 12px 0;
        }

        .activity-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: #818cf8;
          margin-top: 4px;
          box-shadow: 0 0 0 4px rgba(129,140,248,0.08);
          flex-shrink: 0;
        }

        .activity-title {
          font-size: 10px;
          color: #cbd5e1;
          line-height: 1.4;
        }

        .activity-time {
          color: #475569;
          font-size: 9px;
          margin-top: 3px;
        }

        .view-all {
          border: 0;
          background: transparent;
          color: #818cf8;
          display: flex;
          align-items: center;
          gap: 4px;
          font-size: 10px;
          cursor: pointer;
        }

        .mobile-menu {
          display: none;
        }

        .mobile-overlay {
          display: none;
        }

        @media (max-width: 1100px) {
          .stats-grid {
            grid-template-columns: repeat(2, 1fr);
          }

          .main-grid,
          .lower-grid {
            grid-template-columns: 1fr;
          }

          .search {
            display: none;
          }
        }

        @media (max-width: 800px) {
          .sidebar {
            transform: translateX(-100%);
            transition: transform 0.25s ease;
          }

          .sidebar.open {
            transform: translateX(0);
          }

          .main {
            width: 100%;
            margin-left: 0;
          }

          .mobile-menu {
            display: flex;
          }

          .mobile-overlay {
            display: block;
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.55);
            z-index: 40;
          }

          .topbar {
            padding: 0 16px;
          }

          .content {
            padding: 22px 16px;
          }

          .hero {
            align-items: flex-start;
            flex-direction: column;
          }

          .profile-name {
            display: none;
          }
        }

        @media (max-width: 520px) {
          .stats-grid {
            grid-template-columns: 1fr;
          }

          .topbar-left .breadcrumb {
            display: none;
          }

          .subscription-info {
            grid-template-columns: 1fr;
          }

          .hero h1 {
            font-size: 26px;
          }

          .profile-button {
            padding-right: 4px;
          }
        }
      `}</style>

      {sidebarOpen && (
        <div
          className="mobile-overlay"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
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

        <nav className="nav-list">
          {navItems.map((item) => (
          <button
            key={item.label}
            className={`nav-item ${item.active ? "active" : ""}`}
            type="button"
            onClick={() => {
              setSidebarOpen(false);

              if (item.label === "Dashboard") {
                navigate("/dashboard");
              } else if (item.label === "Subscriptions") {
                navigate("/subscriptions");
              } else if (item.label === "Invoices") {
                navigate("/invoices");
              } else if (item.label === "Usage") {
                navigate("/usage");

              } else if (item.label === "Analytics") {
                navigate("/analytics");
              } else if (item.label === "Team") {
                navigate("/team");
              }

            }}
          >
            {item.icon}
            <span>{item.label}</span>
          </button>
          ))}
        </nav>

        <div className="nav-title" style={{ marginTop: 25 }}>
          Management
        </div>

        <nav className="nav-list">
          <button className="nav-item" type="button">
            <IconBell />
            <span>Notifications</span>
          </button>

          <button className="nav-item" type="button">
            <IconSettings />
            <span>Settings</span>
          </button>
        </nav>

        <div className="sidebar-bottom">
          <div className="upgrade-card">
            <div className="upgrade-title">Need more power?</div>

            <div className="upgrade-text">
              Upgrade your plan to unlock higher usage limits and advanced
              billing features.
            </div>

            <button className="upgrade-button" type="button">
              View plans
            </button>
          </div>

          <button
            className="nav-item"
            type="button"
            onClick={() => void logout()}
          >
            <IconLogout />
            <span>Sign out</span>
          </button>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="icon-button mobile-menu"
              type="button"
              onClick={() => setSidebarOpen(true)}
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

            <button className="icon-button" type="button">
              <IconBell />
              <span className="notification-dot" />
            </button>

            <div className="profile">
              <button
                className="profile-button"
                type="button"
                onClick={() => setProfileOpen((value) => !value)}
              >
                <div className="avatar">{initials}</div>
                <span className="profile-name">{displayName}</span>
                <span style={{ color: "#64748b" }}>⌄</span>
              </button>

              {profileOpen && (
                <div className="profile-menu">
                  <div className="profile-menu-header">
                    <div className="profile-menu-name">
                      {displayName}
                    </div>

                    <div className="profile-menu-email">
                      {user?.email || "Account"}
                    </div>
                  </div>

                  <button className="menu-button" type="button">
                    <IconSettings size={15} />
                    Account settings
                  </button>

                  <button
                    className="menu-button logout"
                    type="button"
                    onClick={() => void logout()}
                  >
                    <IconLogout size={15} />
                    Sign out
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        <section className="content">
          <div className="hero">
            <div>
              <div className="hero-eyebrow">Financial overview</div>

              <h1>
                Good morning,{" "}
                {user?.first_name || "there"}.
              </h1>

              <p>
                Here's what's happening with your billing and subscriptions.
              </p>
            </div>

            {isFinance && (
              <button
                type="button"
                className="primary-button"
                onClick={() => navigate("/invoices")}
              >
                <IconPlus />
                Create invoice
              </button>
            )}
          </div>

          <section className="stats-grid">
            <article className="stat-card">
              <div className="stat-top">
                <span className="stat-label">Monthly Recurring Revenue</span>

                <div className="stat-icon">
                  <IconChart size={17} />
                </div>
              </div>

              <div className="stat-value">
                {analytics
                  ? `${analytics.currency} ${Number(analytics.mrr).toFixed(2)}`
                  : "—"}
              </div>

              <div className="stat-bottom">
                <span className="neutral">
                  {analytics?.current_subscription?.interval || "—"}
                </span>

                <span>billing interval</span>
              </div>

            </article>

            <article className="stat-card">
              <div className="stat-top">
                <span className="stat-label">Total Paid</span>

                <div className="stat-icon">
                  <IconCreditCard size={17} />
                </div>
              </div>

              <div className="stat-value">
                {analytics
                  ? `${analytics.currency} ${(
                      analytics.total_paid !== undefined
                        ? Number(analytics.total_paid)
                        : analytics.revenue_trend.reduce(
                            (total, item) =>
                              total + Number(item.revenue || 0),
                            0,
                          )
                    ).toFixed(2)}`
                  : "—"}
              </div>

              <div className="stat-bottom">
                <span className="neutral">
                  {analytics?.currency || "—"}
                </span>

                <span>all payments received</span>
              </div>

            </article>

            <article className="stat-card">
              <div className="stat-top">
                <span className="stat-label">API Usage</span>

                <div className="stat-icon">
                  <IconChart size={17} />
                </div>
              </div>

              <div className="stat-value">
                {usage && usage.limit > 0
                  ? `${Math.min((usage.used / usage.limit) * 100, 100).toFixed(1)}%`
                  : "—"}
              </div>

              <div className="stat-bottom">
                <span className="neutral">
                  {usage ? usage.used.toLocaleString() : "—"}
                </span>

                <span>
                  of {usage ? usage.limit.toLocaleString() : "—"} requests
                </span>
              </div>
            </article>

            <article className="stat-card">
              <div className="stat-top">
                <span className="stat-label">Active Subscription</span>

                <div className="stat-icon">
                  <IconCreditCard size={17} />
                </div>
              </div>

              <div className="stat-value">
                {subscription?.plan?.code || "—"}
              </div>

              <div className="stat-bottom">
                <span className="positive">
                  {subscription?.status || "—"}
                </span>

                <span>
                  {subscription?.interval === "ANNUAL"
                    ? "annual plan"
                    : "monthly plan"}
                </span>
              </div>
            </article>
          </section>

          <section className="main-grid">
            <article className="panel">
              <div className="panel-header">
                <div>
                  <div className="panel-title">Revenue overview</div>

                  <div className="panel-subtitle">
                    Monthly revenue performance
                  </div>
                </div>

                <select className="period-select" defaultValue="6">
                  <option value="6">Last 6 months</option>
                  <option value="12">Last 12 months</option>
                  <option value="3">Last 3 months</option>
                </select>
              </div>

              <div className="chart-container">
                {revenueChartData.length > 0 ? (
                  <svg
                    className="chart-svg"
                    viewBox="0 0 760 260"
                    preserveAspectRatio="none"
                  >
                    <defs>
                      <linearGradient
                        id="revenueGradient"
                        x1="0"
                        y1="0"
                        x2="0"
                        y2="1"
                      >
                        <stop
                          offset="0%"
                          stopColor="#818cf8"
                          stopOpacity="0.28"
                        />
                        <stop
                          offset="100%"
                          stopColor="#818cf8"
                          stopOpacity="0"
                        />
                      </linearGradient>
                    </defs>

                    <line
                      className="chart-grid-line"
                      x1="40"
                      y1="35"
                      x2="745"
                      y2="35"
                    />

                    <line
                      className="chart-grid-line"
                      x1="40"
                      y1="90"
                      x2="745"
                      y2="90"
                    />

                    <line
                      className="chart-grid-line"
                      x1="40"
                      y1="145"
                      x2="745"
                      y2="145"
                    />

                    <line
                      className="chart-grid-line"
                      x1="40"
                      y1="200"
                      x2="745"
                      y2="200"
                    />

                    <path
                      className="chart-area"
                      d={`
                        M ${revenueChartData[0].x} ${revenueChartData[0].y}
                        ${revenueChartData
                          .slice(1)
                          .map(
                            (point) =>
                              `L ${point.x} ${point.y}`,
                          )
                          .join(" ")}
                        L ${revenueChartData[revenueChartData.length - 1].x} 220
                        L ${revenueChartData[0].x} 220
                        Z
                      `}
                      fill="url(#revenueGradient)"
                    />

                    <path
                      className="chart-line"
                      d={`
                        M ${revenueChartData[0].x} ${revenueChartData[0].y}
                        ${revenueChartData
                          .slice(1)
                          .map(
                            (point) =>
                              `L ${point.x} ${point.y}`,
                          )
                          .join(" ")}
                      `}
                      fill="none"
                      stroke="#818cf8"
                      strokeWidth="3"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />

                    {revenueChartData.map((point, index) => (
                      <circle
                        key={`${point.month}-${index}`}
                        className="chart-point"
                        cx={point.x}
                        cy={point.y}
                        r="4"
                        style={{
                          animationDelay: `${0.35 + index * 0.08}s`,
                        }}
                      />
                    ))}

                    {revenueChartData.map((point, index) => (
                      <text
                        key={`label-${point.month}-${index}`}
                        className="chart-label"
                        x={point.x}
                        y="242"
                        textAnchor="middle"
                      >
                        {point.label}
                      </text>
                    ))}
                  </svg>
                ) : (
                  <div
                    style={{
                      height: "100%",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: "#64748b",
                      fontSize: "12px",
                    }}
                  >
                    No revenue data available yet.
                  </div>
                )}
              </div>
            </article>

            <article className="panel">
              <div className="panel-header">
                <div>
                  <div className="panel-title">Current subscription</div>

                  <div className="panel-subtitle">
                    Your active billing plan
                  </div>
                </div>

                <button
                  type="button"
                  className="manage-link"
                  onClick={() => navigate("/subscriptions")}
                >
                  Manage
                  <IconArrowRight size={16} />
                </button>
              </div>

              <div className="subscription-body">
                <div className="subscription-plan">
                  <div className="plan-icon">
                    {subscription?.plan?.code?.charAt(0) || "—"}
                  </div>

                  <div>
                    <div className="plan-name">
                      {subscription?.plan?.name || "—"}
                    </div>

                    <div className="plan-description">
                      {subscription?.plan?.description || "—"}
                    </div>
                  </div>

                  <div className="status-pill">
                    {subscription?.status || "—"}
                  </div>
                </div>

                <div className="subscription-info">
                  <div className="info-box">
                    <div className="info-label">Billing cycle</div>
                    <div className="info-value">
                      {subscription?.interval === "ANNUAL"
                        ? "Annual"
                        : "Monthly"}
                    </div>
                  </div>

                  <div className="info-box">
                    <div className="info-label">Next billing</div>
                    <div className="info-value">
                      {subscription?.current_period_end
                        ? new Date(
                            subscription.current_period_end,
                          ).toLocaleDateString()
                        : "—"}
                    </div>
                  </div>

                  <div className="info-box">
                    <div className="info-label">Plan price</div>
                    <div className="info-value">
                      {subscription?.plan
                        ? `USD ${
                            subscription.interval === "ANNUAL"
                              ? subscription.plan.annual_price
                              : subscription.plan.monthly_price
                          }`
                        : "—"}
                    </div>
                  </div>

                  <div className="info-box">
                    <div className="info-label">Status</div>
                    <div className="info-value">
                      {subscription?.status || "—"}
                    </div>
                  </div>
                </div>

                <div className="usage-section">
                  <div className="usage-header">
                    <span className="usage-title">
                      API request usage
                    </span>

                    <span className="usage-number">
                      {usage
                        ? `${usage.used.toLocaleString()} / ${usage.limit.toLocaleString()}`
                        : "—"}
                    </span>
                  </div>

                  <div className="progress">
                    <div
                        className="progress-fill"
                        style={{
                          width: usage
                            ? `${Math.min(
                                (usage.used / usage.limit) * 100,
                                100,
                              )}%`
                            : "0%",
                        }}
                      />
                  </div>
                  <div className="usage-footer">
                    <span>
                      {usage && usage.limit > 0
                        ? `${Math.min(
                            (usage.used / usage.limit) * 100,
                            100,
                          ).toFixed(3)}% used`
                        : "—"}
                    </span>

                    <span>
                      {usage
                        ? `${usage.remaining.toLocaleString()} remaining`
                        : "—"}
                    </span>
                  </div>
                </div>
              </div>
            </article>
          </section>

          <section className="lower-grid">
            <article className="panel">
              <div className="panel-header">
                <div>
                  <div className="panel-title">Recent invoices</div>

                  <div className="panel-subtitle">
                    Your latest billing activity
                  </div>
                </div>

                <button
                  className="view-all"
                  type="button"
                  onClick={() => navigate("/invoices")}
                >
                  View all
                  <IconArrowRight size={13} />
                </button>
              </div>

              <div className="invoice-list">
                {invoices.slice(0, 3).map((invoice) => (
                  <div className="invoice-row" key={invoice.id}>
                    <div className="invoice-left">
                      <div className="invoice-icon">
                        <IconInvoice size={16} />
                      </div>

                      <div>
                        <div className="invoice-number">
                          {invoice.invoice_number}
                        </div>

                        <div className="invoice-date">
                          {new Date(invoice.issue_date).toLocaleDateString(
                            "en-US",
                            {
                              month: "long",
                              day: "numeric",
                              year: "numeric",
                            },
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="invoice-right">
                      <div className="invoice-amount">
                        {invoice.currency}{" "}
                        {Number(invoice.total).toFixed(2)}
                      </div>

                      <div
                        className={
                          invoice.status.toLowerCase() === "paid"
                            ? "paid"
                            : "invoice-status"
                        }
                      >
                        {invoice.status}
                      </div>
                    </div>
                  </div>
                ))}

                {invoices.length === 0 && (
                  <div
                    style={{
                      padding: "20px 0",
                      color: "#64748b",
                      fontSize: "11px",
                    }}
                  >
                    No invoices yet.
                  </div>
                )}
              </div>
            </article>

            <article className="panel">
              <div className="panel-header">
                <div>
                  <div className="panel-title">Recent activity</div>

                  <div className="panel-subtitle">
                    Latest account events
                  </div>
                </div>

                <button
                  type="button"
                  className="view-all"
                  onClick={() => navigate("/audit")}
                >
                  View all
                  <IconArrowRight size={16} />
                </button>
              </div>

              <div className="activity-list">
                {activity.slice(0, 3).map((item) => (
                  <div
                    className="activity-item"
                    key={item.id}
                  >
                    <div className="activity-dot" />

                    <div className="activity-content">
                      <div className="activity-title">
                        {item.description ||
                          item.action}
                      </div>

                      <div className="activity-time">
                        {new Date(
                          item.created_at,
                        ).toLocaleString("en-US", {
                          month: "short",
                          day: "numeric",
                          hour: "numeric",
                          minute: "2-digit",
                        })}
                      </div>
                    </div>
                  </div>
                ))}

                {activity.length === 0 && (
                  <div
                    style={{
                      padding: "20px 0",
                      color: "#64748b",
                      fontSize: "11px",
                    }}
                  >
                    No recent activity.
                  </div>
                )}
              </div>
            </article>
          </section>
        </section>
      </main>
    </div>
  );
}

export default Dashboard;