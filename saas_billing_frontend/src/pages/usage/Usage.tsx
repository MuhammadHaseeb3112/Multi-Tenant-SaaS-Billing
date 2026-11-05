import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertCircle,
  CalendarClock,
  Gauge,
  Receipt,
  RefreshCw,
  Server,
  TrendingUp,
} from "lucide-react";

import { useOrganization } from "../../context/OrganizationContext";
import {
  getUsageSummary,
  listOverageCharges,
  recordUsage,
} from "../../api/usage";
import type {
  OverageCharge,
  UsageSummary,
} from "../../api/usage";
import ApiKeysPanel from "./ApiKeysPanel";

import "./Usage.css";

const ADMIN_ROLES = ["OWNER", "ADMIN"];

const formatDay = (value: string | null) =>
  value
    ? new Date(value).toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
      })
    : null;

const formatMoney = (amount: string, currency = "usd") =>
  new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: currency.toUpperCase(),
  }).format(Number(amount));

function Usage() {
  const { activeOrganization } = useOrganization();
  const organizationId = activeOrganization?.id ?? null;

  // Previously this showed the user's FIRST organization's name, not
  // the active one.
  const organization = activeOrganization;
  const isAdmin = ADMIN_ROLES.includes(
    activeOrganization?.role ?? "",
  );

  const [charges, setCharges] = useState<OverageCharge[]>([]);

  const [usage, setUsage] =
    useState<UsageSummary | null>(null);

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const loadUsage = async (showRefresh = false) => {
    if (!organizationId) {
      setLoading(false);
      return;
    }

    try {
      setError("");
      setSuccess("");

      if (showRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }

      const [data, overageCharges] = await Promise.all([
        getUsageSummary(organizationId),
        listOverageCharges(organizationId).catch(() => []),
      ]);

      setUsage(data);
      setCharges(overageCharges);
    } catch (err) {
      console.error("Failed to load usage:", err);
      setError("Unable to load usage data.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadUsage();
  }, [organizationId]);

  const usagePercentage = useMemo(() => {
    if (!usage || usage.limit <= 0) {
      return 0;
    }

    return Math.min(
      (usage.used / usage.limit) * 100,
      100,
    );
  }, [usage]);

  const handleRecordUsage = async () => {
    if (!organizationId) {
      return;
    }

    try {
      setRecording(true);
      setError("");
      setSuccess("");

      await recordUsage(organizationId, 1);

      setSuccess("1 API request recorded manually.");

      await loadUsage();
    } catch (err: any) {
      console.error("Failed to record usage:", err);

      setError(
        err?.response?.data?.detail ||
          "Unable to record usage.",
      );
    } finally {
      setRecording(false);
    }
  };

  if (loading) {
    return (
      <div className="usage-page">
        <div className="usage-loading">
          <Activity
            size={22}
            className="usage-spin"
          />
          <span>Loading usage...</span>
        </div>
      </div>
    );
  }

  if (!organizationId) {
    return (
      <div className="usage-page">
        <div className="usage-empty">
          <AlertCircle size={32} />

          <h2>No organization found</h2>

          <p>
            Create or join an organization before
            viewing usage.
          </p>
        </div>
      </div>
    );
  }

  if (error && !usage) {
    return (
      <div className="usage-page">
        <div className="usage-error">
          <AlertCircle size={32} />

          <h2>Usage unavailable</h2>

          <p>{error}</p>

          <button
            type="button"
            onClick={() => loadUsage()}
            className="usage-retry-btn"
          >
            <RefreshCw size={16} />
            Try Again
          </button>
        </div>
      </div>
    );
  }

  if (!usage) {
    return null;
  }

  return (
    <div className="usage-page">
      <header className="usage-header">
        <div>
          <div className="usage-eyebrow">
            <Gauge size={16} />
            USAGE & METERING
          </div>

          <h1>Usage</h1>

          <p>
            Monitor API request consumption for{" "}
            <strong>
              {organization?.name ??
                "your organization"}
            </strong>
            .
          </p>
        </div>

        <button
          type="button"
          className="usage-refresh-btn"
          onClick={() => loadUsage(true)}
          disabled={refreshing}
        >
          <RefreshCw
            size={17}
            className={
              refreshing ? "usage-spin" : ""
            }
          />

          {refreshing
            ? "Refreshing..."
            : "Refresh"}
        </button>
      </header>

      {error && (
        <div className="usage-alert usage-alert-error">
          <AlertCircle size={17} />
          <span>{error}</span>
        </div>
      )}

      {success && (
        <div className="usage-alert usage-alert-success">
          <TrendingUp size={17} />
          <span>{success}</span>
        </div>
      )}

      {/* MAIN USAGE CARD */}
      <section className="usage-main-card">
        <div className="usage-main-header">
          <div className="usage-resource">
            <div className="usage-resource-icon">
              <Server size={22} />
            </div>

            <div>
              <span>Resource</span>
              <h2>API Requests</h2>
            </div>
          </div>

          <div className="usage-percentage">
            <strong>
              {usagePercentage.toFixed(1)}%
            </strong>

            <span>used</span>
          </div>
        </div>

        <div className="usage-progress-track">
          <div
            className="usage-progress-fill"
            style={{
              width: `${usagePercentage}%`,
            }}
          />
        </div>

        <div className="usage-progress-labels">
          <span>
            {usage.used.toLocaleString()} used
          </span>

          <span>
            {usage.limit.toLocaleString()} included
          </span>
        </div>

        {usage.overage_requests > 0 && (
          <div className="usage-overage-note">
            +{usage.overage_requests.toLocaleString()} requests over
            the limit — billed at the end of the period
            {" "}(est.{" "}
            {formatMoney(usage.estimated_overage_amount)}).
          </div>
        )}
      </section>

      {/* KPI CARDS */}
      <section className="usage-kpi-grid">
        <div className="usage-kpi-card">
          <div className="usage-kpi-icon">
            <Activity size={20} />
          </div>

          <div>
            <span>Used</span>

            <strong>
              {usage.used.toLocaleString()}
            </strong>

            <small>
              API requests this period
            </small>
          </div>
        </div>

        <div className="usage-kpi-card">
          <div className="usage-kpi-icon">
            <Gauge size={20} />
          </div>

          <div>
            <span>Included ({usage.plan})</span>

            <strong>
              {usage.limit.toLocaleString()}
            </strong>

            <small>
              {usage.period_start
                ? `${formatDay(usage.period_start)} – ${
                    formatDay(usage.period_end) ?? "renewal pending"
                  }`
                : "Requests per period"}
            </small>
          </div>
        </div>

        <div className="usage-kpi-card">
          <div className="usage-kpi-icon">
            <TrendingUp size={20} />
          </div>

          <div>
            <span>Remaining</span>

            <strong>
              {usage.remaining.toLocaleString()}
            </strong>

            <small>
              {usage.remaining === 0 && usage.overage_enabled
                ? "Now in paid overage"
                : "Requests available"}
            </small>
          </div>
        </div>

        <div className="usage-kpi-card">
          <div className="usage-kpi-icon">
            <Receipt size={20} />
          </div>

          <div>
            <span>Overage</span>

            <strong>
              {usage.overage_enabled
                ? formatMoney(usage.estimated_overage_amount)
                : "Off"}
            </strong>

            <small>
              {usage.overage_enabled
                ? `${formatMoney(usage.overage_price_per_1000)} per 1,000 extra${
                    usage.max_overage_requests !== null
                      ? ` · cap ${usage.max_overage_requests.toLocaleString()}`
                      : ""
                  }`
                : "Requests over the limit are blocked (429)"}
            </small>
          </div>
        </div>
      </section>

      {isAdmin ? (
        <ApiKeysPanel organizationId={organizationId} />
      ) : (
        <section className="usage-panel">
          <div className="usage-panel-header">
            <div>
              <h2>API Keys</h2>
              <p>
                Only owners and admins can create or revoke API keys.
              </p>
            </div>
          </div>
        </section>
      )}

      {charges.length > 0 && (
        <section className="usage-panel">
          <div className="usage-panel-header">
            <div>
              <h2>Overage Billing History</h2>
              <p>
                Usage above the plan limit, added to your Stripe
                invoices.
              </p>
            </div>
            <CalendarClock size={20} />
          </div>

          <div className="apikey-table-wrap">
            <table className="apikey-table">
              <thead>
                <tr>
                  <th>Period</th>
                  <th>Used</th>
                  <th>Included</th>
                  <th>Overage</th>
                  <th>Amount</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {charges.map((charge) => (
                  <tr key={charge.id}>
                    <td>
                      {formatDay(charge.period_start)} –{" "}
                      {formatDay(charge.period_end)}
                    </td>
                    <td>{charge.used_requests.toLocaleString()}</td>
                    <td>{charge.included_requests.toLocaleString()}</td>
                    <td>{charge.overage_requests.toLocaleString()}</td>
                    <td>
                      {formatMoney(charge.amount, charge.currency)}
                    </td>
                    <td>
                      <span className="apikey-badge apikey-badge-active">
                        {charge.status === "BILLED"
                          ? "On invoice"
                          : "Next invoice"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* MANUAL ADJUSTMENT (owners/admins only; real usage comes from
          API calls made with API keys) */}
      {isAdmin && (
      <section className="usage-panel">
        <div className="usage-panel-header">
          <div>
            <h2>Manual Adjustment</h2>

            <p>
              Record a request by hand (audited). Real usage is
              recorded automatically when your apps call the API.
            </p>
          </div>

          <button
            type="button"
            className="usage-record-btn"
            onClick={handleRecordUsage}
            disabled={recording}
          >
            <Activity size={16} />

            {recording
              ? "Recording..."
              : "Record 1 Request"}
          </button>
        </div>

        <div className="usage-metering-info">
          <div>
            <span>Resource</span>
            <strong>{usage.resource}</strong>
          </div>

          <div>
            <span>Current Usage</span>
            <strong>
              {usage.used.toLocaleString()}
            </strong>
          </div>

          <div>
            <span>Remaining</span>
            <strong>
              {usage.remaining.toLocaleString()}
            </strong>
          </div>
        </div>
      </section>
      )}
    </div>
  );
}

export default Usage;