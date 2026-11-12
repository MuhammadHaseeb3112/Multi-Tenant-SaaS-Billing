import { useNavigate } from "react-router-dom";

import { useLayout } from "../../components/layout/layoutContext";
import { useAuth } from "../../context/AuthContext";
import { useOrganization } from "../../context/OrganizationContext";
import { useOrgRole } from "../../utils/roles";
import RecentActivity from "./components/RecentActivity";
import RecentInvoices from "./components/RecentInvoices";
import RevenueOverview from "./components/RevenueOverview";
import StatsGrid from "./components/StatsGrid";
import SubscriptionPanel from "./components/SubscriptionPanel";
import Topbar from "./components/Topbar";
import { IconPlus } from "./icons";
import { greeting } from "./revenueChart";
import { useDashboardData } from "./useDashboardData";

import "./Dashboard.css";

function DashboardPage() {
  const { user, logout } = useAuth();
  const { activeOrganizationId } = useOrganization();
  const { isFinance } = useOrgRole();
  const navigate = useNavigate();
  const { openSidebar } = useLayout();

  const { usage, subscription, analytics, invoices, activity } =
    useDashboardData(activeOrganizationId);

  const handleLogout = () => {
    void logout();
  };

  return (
    <div className="saas-dashboard">
      <main className="main">
        <Topbar
          user={user}
          onOpenMenu={openSidebar}
          onLogout={handleLogout}
        />

        <section className="content">
          <div className="hero">
            <div>
              <div className="hero-eyebrow">Financial overview</div>

              <h1>
                {greeting()}, {user?.first_name || "there"}.
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

          <StatsGrid
            analytics={analytics}
            usage={usage}
            subscription={subscription}
          />

          <section className="main-grid">
            <RevenueOverview analytics={analytics} />
            <SubscriptionPanel subscription={subscription} usage={usage} />
          </section>

          <section className="lower-grid">
            <RecentInvoices invoices={invoices} />
            <RecentActivity activity={activity} />
          </section>
        </section>
      </main>
    </div>
  );
}

// Remount per organization so the widgets never show the previous
// organization's data while the new one loads.
function Dashboard() {
  const { activeOrganizationId } = useOrganization();

  return <DashboardPage key={activeOrganizationId ?? "none"} />;
}

export default Dashboard;
