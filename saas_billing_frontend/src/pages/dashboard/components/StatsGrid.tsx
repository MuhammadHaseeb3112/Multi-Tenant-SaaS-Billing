import type { AnalyticsOverview } from "../../../api/analytics";
import type { Subscription } from "../../../api/billing";
import type { UsageSummary } from "../../../api/usage";
import { IconChart, IconCreditCard } from "../icons";
import { collectedFromCustomers, usagePercent } from "../revenueChart";

interface StatsGridProps {
  analytics: AnalyticsOverview | null;
  usage: UsageSummary | null;
  subscription: Subscription | null;
}

const money = (currency: string, value: number) =>
  `${currency} ${value.toFixed(2)}`;

export default function StatsGrid({
  analytics,
  usage,
  subscription,
}: StatsGridProps) {
  return (
    <section className="stats-grid">
      <article className="stat-card">
        <div className="stat-top">
          <span className="stat-label">Monthly Recurring Revenue</span>
          <div className="stat-icon">
            <IconChart size={17} />
          </div>
        </div>

        <div className="stat-value">
          {analytics ? money(analytics.currency, Number(analytics.mrr)) : "—"}
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
          <span className="stat-label">Collected from Customers</span>
          <div className="stat-icon">
            <IconCreditCard size={17} />
          </div>
        </div>

        <div className="stat-value">
          {analytics
            ? money(analytics.currency, collectedFromCustomers(analytics))
            : "—"}
        </div>

        <div className="stat-bottom">
          <span className="neutral">{analytics?.currency || "—"}</span>
          <span>invoice payments received</span>
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
            ? `${usagePercent(usage.used, usage.limit).toFixed(1)}%`
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

        <div className="stat-value">{subscription?.plan?.code || "—"}</div>

        <div className="stat-bottom">
          <span className="positive">{subscription?.status || "—"}</span>
          <span>
            {subscription?.interval === "ANNUAL"
              ? "annual plan"
              : "monthly plan"}
          </span>
        </div>
      </article>
    </section>
  );
}
