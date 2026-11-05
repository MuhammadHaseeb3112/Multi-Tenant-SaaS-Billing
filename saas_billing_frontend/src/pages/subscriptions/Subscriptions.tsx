
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  cancelSubscription,
  changeSubscription,
  createCheckout,
  getPlans,
  getSubscription,
  resumeSubscription,
  type BillingPlan,
  type Subscription,
} from "../../api/billing";

import { useOrganization } from "../../context/OrganizationContext";
import { useOrgRole } from "../../utils/roles";

import "./Subscriptions.css";

type BillingInterval = "MONTHLY" | "ANNUAL";

function formatPrice(price: string | number) {
  return new Intl.NumberFormat("en-PK").format(Number(price));
}

function CheckIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
    >
      <path d="m5 12 4 4L19 6" />
    </svg>
  );
}

function SparkleIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
    >
      <path d="m12 3-1.8 5.2L5 10l5.2 1.8L12 17l1.8-5.2L19 10l-5.2-1.8L12 3Z" />
      <path d="m19 16-.8 2.2L16 19l2.2.8L19 19l-2.2-.8L19 16Z" />
    </svg>
  );
}

function CreditCardIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
    >
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="M3 10h18" />
      <path d="M7 15h4" />
    </svg>
  );
}

function ArrowIcon() {
  return (
    <svg
      width="16"
      height="16"
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

function Subscriptions() {

  const { activeOrganizationId } = useOrganization();
  const organizationId = activeOrganizationId;

  // Plan changes, checkout, cancel and resume are OWNER/ADMIN only.
  const { isAdmin } = useOrgRole();

  const [interval, setInterval] =
    useState<BillingInterval>("MONTHLY");

  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [subscription, setSubscription] =
    useState<Subscription | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [selectedPlan, setSelectedPlan] =
    useState<string | null>(null);

  const [error, setError] = useState<string | null>(null);

  const [message, setMessage] =
    useState<string | null>(null);

  const loadBillingData = useCallback(async () => {
  setIsLoading(true);
  setError(null);

  try {
    // ---------------------------------------------------------
    // 1. Always load available plans
    // ---------------------------------------------------------
    const plansResponse = await getPlans();

    setPlans(plansResponse);

    // ---------------------------------------------------------
    // 2. Load organization subscription only when
    //    an organization is available
    // ---------------------------------------------------------
    if (!organizationId) {
      setSubscription(null);
      return;
    }

    try {
      const subscriptionResponse =
        await getSubscription(organizationId);

      setSubscription(subscriptionResponse);

      if (
        subscriptionResponse.interval ===
        "ANNUAL"
      ) {
        setInterval("ANNUAL");
      }
    } catch (subscriptionError: any) {
      /*
       * Organization may not have a subscription yet.
       */
      if (
        subscriptionError?.response?.status === 404
      ) {
        setSubscription(null);
      } else {
        throw subscriptionError;
      }
    }
  } catch (requestError: any) {
    const detail =
      requestError?.response?.data?.detail ||
      "Unable to load billing information.";

    setError(detail);
  } finally {
    setIsLoading(false);
  }
}, [organizationId]);

  useEffect(() => {
    void loadBillingData();
  }, [loadBillingData]);

  const currentPlanCode =
    subscription?.plan?.code ?? "FREE";

  const currentPlanData = useMemo(() => {
    return (
      plans.find(
        (plan) => plan.code === currentPlanCode,
      ) ?? null
    );
  }, [plans, currentPlanCode]);

  const currentPrice = currentPlanData
    ? interval === "MONTHLY"
      ? currentPlanData.monthly_price
      : currentPlanData.annual_price
    : 0;

  const handlePlanAction = async (
    planCode: string,
  ) => {
    if (!organizationId) {
      setError("No organization is available.");
      return;
    }

    setSelectedPlan(planCode);
    setActionLoading(true);
    setError(null);
    setMessage(null);

    try {
      /*
       * FREE plan:
       * The backend explicitly handles FREE differently.
       */
      if (planCode === "FREE") {
        setError(
          "Free plan changes are handled through subscription cancellation.",
        );

        return;
      }

      /*
       * No live Stripe subscription (never paid, or the old one
       * was canceled): start Stripe Checkout. A canceled Stripe
       * subscription cannot be changed, so it needs a new checkout.
       */
      if (
        !subscription?.stripe_subscription_id ||
        subscription.status === "CANCELED"
      ) {
        const response = await createCheckout(
          organizationId,
          planCode,
          interval,
        );

        if (response.checkout_url) {
          window.location.href =
            response.checkout_url;
        }

        return;
      }

      /*
       * Existing subscription:
       * Change plan or billing interval.
       */
      const response = await changeSubscription(
        organizationId,
        planCode,
        interval,
      );

      setMessage(
        response.detail ||
          "Subscription change submitted successfully.",
      );

      await loadBillingData();
    } catch (requestError: any) {
      const detail =
        requestError?.response?.data?.detail ||
        requestError?.response?.data?.plan_code?.[0] ||
        requestError?.response?.data?.interval?.[0] ||
        "Unable to process the subscription request.";

      setError(detail);
    } finally {
      setActionLoading(false);
      setSelectedPlan(null);
    }
  };

  const handleCancel = async () => {
    if (!organizationId) {
      return;
    }

    setActionLoading(true);
    setError(null);
    setMessage(null);

    try {
      const response =
        await cancelSubscription(
          organizationId,
        );

      setMessage(
        response.detail ||
          "Subscription cancellation scheduled.",
      );

      await loadBillingData();
    } catch (requestError: any) {
      const detail =
        requestError?.response?.data?.detail ||
        "Unable to cancel the subscription.";

      setError(detail);
    } finally {
      setActionLoading(false);
    }
  };

  const handleResume = async () => {
    if (!organizationId) {
      return;
    }

    setActionLoading(true);
    setError(null);
    setMessage(null);

    try {
      const response =
        await resumeSubscription(
          organizationId,
        );

      setMessage(
        response.detail ||
          "Subscription resumed successfully.",
      );

      await loadBillingData();
    } catch (requestError: any) {
      const detail =
        requestError?.response?.data?.detail ||
        "Unable to resume the subscription.";

      setError(detail);
    } finally {
      setActionLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="subscriptions-page">
        <div className="subscriptions-container">
          <div className="subscriptions-header">
            <div>
              <div className="page-eyebrow">
                <SparkleIcon />
                BILLING & SUBSCRIPTION
              </div>

              <h1>Loading your plans...</h1>

              <p>
                Fetching your latest billing information.
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="subscriptions-page">
      <div className="subscriptions-glow subscriptions-glow-one" />
      <div className="subscriptions-glow subscriptions-glow-two" />

      <div className="subscriptions-container">

        {/* Header */}
        <header className="subscriptions-header">
          <div>
            <div className="page-eyebrow">
              <SparkleIcon />
              BILLING & SUBSCRIPTION
            </div>

            <h1>Plans that scale with you</h1>

            <p>
              Manage your subscription, billing interval,
              and payment plan from one place.
            </p>
          </div>

          <div className="billing-toggle-wrapper">
            <span>Billing</span>

            <div className="billing-toggle">
              <button
                className={
                  interval === "MONTHLY"
                    ? "active"
                    : ""
                }
                onClick={() =>
                  setInterval("MONTHLY")
                }
              >
                Monthly
              </button>

              <button
                className={
                  interval === "ANNUAL"
                    ? "active"
                    : ""
                }
                onClick={() =>
                  setInterval("ANNUAL")
                }
              >
                Annual
                <span className="save-badge">
                  Save
                </span>
              </button>
            </div>
          </div>
        </header>

        {/* Messages */}
        {error && (
          <div className="billing-error">
            {error}
          </div>
        )}

        {message && (
          <div className="billing-success">
            {message}
          </div>
        )}

        {!isAdmin && (
          <div className="billing-info">
            Only owners and admins can change, cancel or resume the
            subscription. You can view the current plan.
          </div>
        )}

        {/* Current subscription */}
        <section className="current-subscription-card">
          <div className="current-subscription-left">
            <div className="subscription-icon">
              <CreditCardIcon />
            </div>

            <div>
              <div className="current-label">
                CURRENT SUBSCRIPTION
              </div>

              <div className="current-plan-row">
                <h2>
                  {currentPlanData?.name ||
                    currentPlanCode}
                </h2>

                <span className="status-badge">
                  <span className="status-dot" />

                  {subscription?.status
                    ? subscription.status.toUpperCase()
                    : "ACTIVE"}
                </span>
              </div>

              <p>
                {currentPlanData?.description ||
                  "Your current billing subscription."}
              </p>
            </div>
          </div>

          <div className="current-subscription-right">
            <div className="current-price">
              <span className="currency">
                USD
              </span>

              <strong>
                {formatPrice(currentPrice)}
              </strong>

              <span className="period">
                /{" "}
                {interval === "MONTHLY"
                  ? "month"
                  : "year"}
              </span>
            </div>

            <div className="next-billing">
              <span>Next billing</span>

              <strong>
                {subscription?.current_period_end
                  ? new Date(
                      subscription.current_period_end,
                    ).toLocaleDateString("en-PK", {
                      day: "2-digit",
                      month: "short",
                      year: "numeric",
                    })
                  : "—"}
              </strong>
            </div>
          </div>
        </section>

        {/* Cancellation status */}
        {subscription?.cancel_at_period_end && (
          <div className="billing-warning">
            <div>
              <strong>
                Cancellation scheduled
              </strong>

              <p>
                Your subscription will remain active
                until the end of the current billing
                period.
              </p>
            </div>

            {isAdmin && (
              <button
                onClick={() => void handleResume()}
                disabled={actionLoading}
              >
                {actionLoading
                  ? "Processing..."
                  : "Resume subscription"}
              </button>
            )}
          </div>
        )}

        {/* Plans */}
        <section className="plans-section">
          <div className="section-heading">
            <div>
              <h2>Choose your plan</h2>

              <p>
                Upgrade or change your plan whenever
                your business needs.
              </p>
            </div>

            {isAdmin &&
              subscription &&
              !subscription.cancel_at_period_end &&
              subscription.stripe_subscription_id && (
                <button
                  className="cancel-subscription-button"
                  onClick={() =>
                    void handleCancel()
                  }
                  disabled={actionLoading}
                >
                  {actionLoading
                    ? "Processing..."
                    : "Cancel subscription"}
                </button>
              )}
          </div>

          <div className="plans-grid">
            {plans.map((plan) => {
              const isCurrent =
                plan.code === currentPlanCode;

              const isPopular =
                plan.code === "PRO";

              const price =
                interval === "MONTHLY"
                  ? plan.monthly_price
                  : plan.annual_price;

              const isProcessing =
                actionLoading &&
                selectedPlan === plan.code;

              let buttonText = "Choose plan";

              if (isCurrent) {
                buttonText = "Current plan";
              } else if (isProcessing) {
                buttonText = "Processing...";
              } else if (
                plan.code === "ENTERPRISE"
              ) {
                buttonText =
                  currentPlanCode === "PRO"
                    ? "Upgrade to Enterprise"
                    : "Choose Enterprise";
              } else if (
                plan.code === "PRO"
              ) {
                buttonText =
                  currentPlanCode === "ENTERPRISE"
                    ? "Switch to Professional"
                    : "Choose Professional";
              }

              return (
                <article
                  key={plan.code}
                  className={`plan-card ${
                    isPopular
                      ? "popular-plan"
                      : ""
                  } ${
                    isCurrent
                      ? "current-plan"
                      : ""
                  }`}
                >
                  {isPopular && (
                    <div className="popular-ribbon">
                      <SparkleIcon />
                      MOST POPULAR
                    </div>
                  )}

                  <div className="plan-card-top">
                    <div
                      className={`plan-avatar ${plan.code.toLowerCase()}`}
                    >
                      {plan.code === "FREE"
                        ? "F"
                        : plan.code === "PRO"
                        ? "P"
                        : "E"}
                    </div>

                    {isCurrent && (
                      <span className="current-pill">
                        CURRENT
                      </span>
                    )}
                  </div>

                  <h3>{plan.name}</h3>

                  <p className="plan-description">
                    {plan.description}
                  </p>

                  <div className="plan-price">
                    <span>USD</span>

                    <strong>
                      {formatPrice(price)}
                    </strong>

                    <small>
                      /{" "}
                      {interval === "MONTHLY"
                        ? "month"
                        : "year"}
                    </small>
                  </div>

                  <div className="plan-divider" />

                  <div className="feature-title">
                    What's included
                  </div>

                  <ul className="feature-list">
                    <li>
                      <CheckIcon />

                      {formatPrice(
                        plan.api_request_limit,
                      )}{" "}
                      API requests
                    </li>

                    <li>
                      <CheckIcon />
                      Subscription management
                    </li>

                    <li>
                      <CheckIcon />
                      Invoice management
                    </li>

                    <li>
                      <CheckIcon />
                      Billing analytics
                    </li>

                    {plan.code !== "FREE" && (
                      <li>
                        <CheckIcon />
                        Priority billing support
                      </li>
                    )}
                  </ul>

                  {(isAdmin || isCurrent) && (
                  <button
                    className={`plan-action ${
                      isCurrent
                        ? "current-action"
                        : ""
                    }`}
                    disabled={
                      isCurrent ||
                      actionLoading
                    }
                    onClick={() =>
                      void handlePlanAction(
                        plan.code,
                      )
                    }
                  >
                    {buttonText}

                    {!isCurrent &&
                      !isProcessing && (
                        <ArrowIcon />
                      )}
                  </button>
                  )}
                </article>
              );
            })}
          </div>
        </section>

        {/* Payment information */}
        <section className="billing-info-card">
          <div className="billing-info-icon">
            <CreditCardIcon />
          </div>

          <div>
            <h3>
              Secure billing with Stripe
            </h3>

            <p>
              Payments are securely processed through
              Stripe. Your card details are never stored
              on our servers.
            </p>
          </div>

          <div className="stripe-badge">
            STRIPE
          </div>
        </section>

        {/* Footer */}
        <div className="subscription-footer">
          <span>
            Need help choosing a plan?
          </span>

          <button>
            Contact support
          </button>
        </div>
      </div>
    </div>
  );
}

export default Subscriptions;