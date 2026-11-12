import { useContext } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { OrganizationContext } from "../../context/OrganizationContext";
import { usePastDueSubscription } from "../../hooks/usePastDueSubscription";

const formatDate = (value: string) =>
  new Date(value).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

/**
 * Shown on every signed-in page while the workspace's subscription
 * payment is overdue, so nobody is surprised by the downgrade.
 */
export default function BillingAlert() {
  const subscription = usePastDueSubscription();
  // Read the context directly: the layout also renders without a
  // workspace (and in tests), where there is simply nothing to warn about.
  const role = useContext(OrganizationContext)?.activeOrganization?.role;
  const isAdmin = role === "OWNER" || role === "ADMIN";
  const navigate = useNavigate();
  const { pathname } = useLocation();

  if (!subscription) {
    return null;
  }

  const deadline = subscription.grace_period_end
    ? ` by ${formatDate(subscription.grace_period_end)}`
    : " soon";

  return (
    <div className="billing-alert" role="alert">
      <div className="billing-alert-text">
        <strong>Payment failed.</strong>{" "}
        We could not charge the card for the {subscription.plan.name} plan.
        {isAdmin
          ? ` Update the card or pay the open invoice${deadline}, or this workspace moves to the Free plan.`
          : ` Unless it is paid${deadline}, this workspace moves to the Free plan. Ask an owner or admin to update billing.`}
      </div>

      {isAdmin && pathname !== "/subscriptions" && (
        <button
          type="button"
          className="billing-alert-action"
          onClick={() => navigate("/subscriptions")}
        >
          Review billing
        </button>
      )}
    </div>
  );
}
