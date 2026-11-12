import { useNavigate } from "react-router-dom";

import type { Subscription } from "../../../api/billing";
import type { UsageSummary } from "../../../api/usage";
import { IconArrowRight } from "../icons";
import { usagePercent } from "../revenueChart";

interface SubscriptionPanelProps {
  subscription: Subscription | null;
  usage: UsageSummary | null;
}

export default function SubscriptionPanel({
  subscription,
  usage,
}: SubscriptionPanelProps) {
  const navigate = useNavigate();
  const percent = usage ? usagePercent(usage.used, usage.limit) : 0;

  return (
    <article className="panel">
      <div className="panel-header">
        <div>
          <div className="panel-title">Current subscription</div>
          <div className="panel-subtitle">Your active billing plan</div>
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
            <div className="plan-name">{subscription?.plan?.name || "—"}</div>
            <div className="plan-description">
              {subscription?.plan?.description || "—"}
            </div>
          </div>

          <div className="status-pill">{subscription?.status || "—"}</div>
        </div>

        <div className="subscription-info">
          <div className="info-box">
            <div className="info-label">Billing cycle</div>
            <div className="info-value">
              {subscription?.interval === "ANNUAL" ? "Annual" : "Monthly"}
            </div>
          </div>

          <div className="info-box">
            <div className="info-label">Next billing</div>
            <div className="info-value">
              {subscription?.current_period_end
                ? new Date(subscription.current_period_end).toLocaleDateString()
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
            <div className="info-value">{subscription?.status || "—"}</div>
          </div>
        </div>

        <div className="usage-section">
          <div className="usage-header">
            <span className="usage-title">API request usage</span>
            <span className="usage-number">
              {usage
                ? `${usage.used.toLocaleString()} / ${usage.limit.toLocaleString()}`
                : "—"}
            </span>
          </div>

          <div className="progress">
            <div className="progress-fill" style={{ width: `${percent}%` }} />
          </div>

          <div className="usage-footer">
            <span>
              {usage && usage.limit > 0 ? `${percent.toFixed(1)}% used` : "—"}
            </span>
            <span>
              {usage ? `${usage.remaining.toLocaleString()} remaining` : "—"}
            </span>
          </div>
        </div>
      </div>
    </article>
  );
}
