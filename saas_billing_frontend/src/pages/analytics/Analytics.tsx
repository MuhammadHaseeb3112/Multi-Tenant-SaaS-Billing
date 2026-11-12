import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertCircle,
  BarChart3,
  CalendarDays,
  CreditCard,
  DollarSign,
  RefreshCw,
  TrendingUp,
} from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useOrganization } from "../../context/OrganizationContext";
import { getAnalyticsOverview } from "../../api/analytics";
import type { AnalyticsOverview } from "../../api/analytics";
import "./Analytics.css";

function AnalyticsPage() {
  const { activeOrganization } = useOrganization();
  const organizationId = activeOrganization?.id ?? null;

  // Was the user's FIRST organization, not the active one.
  const organization = activeOrganization;

  const [analytics, setAnalytics] =
    useState<AnalyticsOverview | null>(null);

  const [loading, setLoading] = useState(Boolean(organizationId));
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  // Fetches and stores data; sets no state before the request, so it can
  // run straight from the mount effect.
  const fetchAnalytics = useCallback(async () => {
    if (!organizationId) {
      return;
    }

    await getAnalyticsOverview(organizationId)
      .then((data) => {
        setAnalytics(data);
        setError("");
      })
      .catch((err: unknown) => {
        console.error("Failed to load analytics:", err);
        setError("Unable to load analytics data.");
      })
      .finally(() => {
        setLoading(false);
        setRefreshing(false);
      });
  }, [organizationId]);

  useEffect(() => {
    void fetchAnalytics();
  }, [fetchAnalytics]);

  // Retry / Refresh buttons.
  const loadAnalytics = (showRefresh = false) => {
    setError("");

    if (showRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    void fetchAnalytics();
  };

  const revenueChartData = useMemo(() => {
    if (!analytics) {
      return [];
    }

    return analytics.revenue_trend.map((item) => ({
      month: item.month,
      revenue: Number(item.revenue),
    }));
  }, [analytics]);

  if (loading) {
    return (
      <div className="analytics-page">
        <div className="analytics-loading">
          <Activity size={22} className="analytics-spin" />
          <span>Loading analytics...</span>
        </div>
      </div>
    );
  }

  if (!organizationId) {
    return (
      <div className="analytics-page">
        <div className="analytics-empty">
          <AlertCircle size={32} />
          <h2>No organization found</h2>
          <p>
            Create or join an organization before viewing analytics.
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="analytics-page">
        <div className="analytics-error">
          <AlertCircle size={32} />
          <h2>Analytics unavailable</h2>
          <p>{error}</p>

          <button
            type="button"
            onClick={() => loadAnalytics()}
            className="analytics-retry-btn"
          >
            <RefreshCw size={16} />
            Try Again
          </button>
        </div>
      </div>
    );
  }

  if (!analytics) {
    return null;
  }

  const {
    mrr,
    currency,
    current_subscription,
    subscription_breakdown,
  } = analytics;

  // One subscription per organization: show its actual status
  // (previously anything but ACTIVE, e.g. TRIALING / PAST_DUE, showed
  // "NO ACTIVE SUBSCRIPTION").
  const subscriptionStatus =
    subscription_breakdown.active > 0
      ? "ACTIVE"
      : subscription_breakdown.trialing > 0
        ? "TRIALING"
        : subscription_breakdown.past_due > 0
          ? "PAST DUE"
          : subscription_breakdown.canceled > 0
            ? "CANCELED"
            : "NO SUBSCRIPTION";

  // Customer money and platform fees, kept apart. The trend sum is
  // only a fallback for older backends.
  const collectedFromCustomers = Number(
    analytics.collected_from_customers ??
      analytics.total_paid ??
      analytics.revenue_trend.reduce(
        (sum, item) => sum + Number(item.revenue),
        0,
      ),
  );

  const paidToPlatform = Number(analytics.paid_to_platform ?? 0);
  const openInvoices = analytics.open_invoices;

  const latestMonth =
    analytics.revenue_trend.length > 0
      ? analytics.revenue_trend[analytics.revenue_trend.length - 1]
          .month
      : null;

  const latestRevenue =
    analytics.revenue_trend.length > 0
      ? Number(
          analytics.revenue_trend[
            analytics.revenue_trend.length - 1
          ].revenue,
        )
      : 0;

  return (
    <div className="analytics-page">
      <header className="analytics-header">
        <div>
          <div className="analytics-eyebrow">
            <BarChart3 size={16} />
            BUSINESS ANALYTICS
          </div>

          <h1>Analytics</h1>

          <p>
            Track the plan, recurring cost and payments of{" "}
            <strong>
              {organization?.name ?? "your organization"}
            </strong>
            .
          </p>
        </div>

        <button
          type="button"
          className="analytics-refresh-btn"
          onClick={() => loadAnalytics(true)}
          disabled={refreshing}
        >
          <RefreshCw
            size={17}
            className={refreshing ? "analytics-spin" : ""}
          />
          {refreshing ? "Refreshing..." : "Refresh"}
        </button>
      </header>

      {/* KPI CARDS */}
      <section className="analytics-kpi-grid">
        <div className="analytics-kpi-card">
          <div className="analytics-kpi-icon">
            <DollarSign size={20} />
          </div>

          <div className="analytics-kpi-content">
            <span>Monthly Recurring Revenue</span>
            <strong>
              {currency} {Number(mrr).toFixed(2)}
            </strong>

            <small>
              Recurring amount of the current plan
            </small>
          </div>
        </div>

        <div className="analytics-kpi-card">
          <div className="analytics-kpi-icon">
            <CreditCard size={20} />
          </div>

          <div className="analytics-kpi-content">
            <span>Current Plan</span>
            <strong>{current_subscription.plan ?? "None"}</strong>

            <small>
              {current_subscription.interval
                ? `Billed ${current_subscription.interval.toLowerCase()}`
                : "No billing interval"}
            </small>
          </div>
        </div>

        <div className="analytics-kpi-card">
          <div className="analytics-kpi-icon">
            <TrendingUp size={20} />
          </div>

          <div className="analytics-kpi-content">
            <span>Collected from Customers</span>
            <strong>
              {currency} {collectedFromCustomers.toFixed(2)}
            </strong>

            <small>
              Invoice payments received (Stripe + manual)
            </small>
          </div>
        </div>

        <div className="analytics-kpi-card">
          <div className="analytics-kpi-icon">
            <CreditCard size={20} />
          </div>

          <div className="analytics-kpi-content">
            <span>Paid to Platform</span>
            <strong>
              {currency} {paidToPlatform.toFixed(2)}
            </strong>

            <small>
              Subscription fees for this workspace
            </small>
          </div>
        </div>

        {openInvoices && (
          <div className="analytics-kpi-card">
            <div className="analytics-kpi-icon">
              <TrendingUp size={20} />
            </div>

            <div className="analytics-kpi-content">
              <span>Awaiting Payment</span>
              <strong>
                {currency} {Number(openInvoices.amount).toFixed(2)}
              </strong>

              <small>
                {openInvoices.count === 1
                  ? "1 open customer invoice"
                  : `${openInvoices.count} open customer invoices`}
              </small>
            </div>
          </div>
        )}

        <div className="analytics-kpi-card">
          <div className="analytics-kpi-icon">
            <CalendarDays size={20} />
          </div>

          <div className="analytics-kpi-content">
            <span>Latest Payment Month</span>
            <strong>
              {latestMonth ?? "—"}
            </strong>

            <small>
              {latestMonth
                ? `${currency} ${latestRevenue.toFixed(2)} collected from customers`
                : "No customer payments yet"}
            </small>
          </div>
        </div>
      </section>

      {/* CHART + CURRENT PLAN */}
      <section className="analytics-main-grid">
        <div className="analytics-panel analytics-revenue-panel">
          <div className="analytics-panel-header">
            <div>
              <h2>Revenue Trend</h2>
              <p>Collected from customers per month</p>
            </div>

            <div className="analytics-revenue-value">
              <span>Latest Month</span>
              <strong>
                {currency} {latestRevenue.toFixed(2)}
              </strong>
            </div>
          </div>

          <div className="analytics-chart">
            {revenueChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={revenueChartData}>
                  <CartesianGrid strokeDasharray="3 3" />

                  <XAxis dataKey="month" />

                  <YAxis />

                  <Tooltip
                    formatter={(value) => [
                      `${currency} ${Number(value).toFixed(2)}`,
                      "Revenue",
                    ]}
                  />

                  <Line
                    type="monotone"
                    dataKey="revenue"
                    strokeWidth={3}
                    dot={{ r: 4 }}
                    activeDot={{ r: 6 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="analytics-chart-empty">
                <BarChart3 size={32} />

                <strong>No payments yet</strong>

                <span>
                  Payments will appear here once they are recorded.
                </span>
              </div>
            )}
          </div>
        </div>

        <div className="analytics-panel">
          <div className="analytics-panel-header">
            <div>
              <h2>Current Subscription</h2>
              <p>Your organization's current plan</p>
            </div>
          </div>

          <div className="analytics-plan-card">
            <div className="analytics-plan-icon">
              <CreditCard size={22} />
            </div>

            <div>
              <span>Plan</span>
              <strong>
                {current_subscription.plan ?? "None"}
              </strong>
            </div>
          </div>

          <div className="analytics-detail-list">
            <div>
              <span>Status</span>
              <strong>
                {subscriptionStatus}
              </strong>
            </div>

            <div>
              <span>Billing Interval</span>
              <strong>
                {current_subscription.interval ?? "—"}
              </strong>
            </div>

            <div>
              <span>MRR</span>
              <strong>
                {currency} {Number(mrr).toFixed(2)}
              </strong>
            </div>
          </div>
        </div>
      </section>

    </div>
  );
}

// Remount the page when the active organization changes, so every piece
// of state (loading flags, data, errors) starts fresh for the new org and
// a slow response for the previous org can never overwrite the new one.
function Analytics() {
  const { activeOrganizationId } = useOrganization();

  return <AnalyticsPage key={activeOrganizationId ?? "none"} />;
}

export default Analytics;