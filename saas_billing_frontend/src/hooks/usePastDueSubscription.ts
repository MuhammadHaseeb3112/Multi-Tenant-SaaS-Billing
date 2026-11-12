import { useCallback, useContext, useEffect, useState } from "react";

import { getSubscription } from "../api/billing";
import type { Subscription } from "../api/billing";
import { OrganizationContext } from "../context/OrganizationContext";

// The warning re-checks on its own, when the window regains focus, and
// whenever a page changes the subscription (plan change, cancel...).
const REFRESH_MS = 60_000;

const CHANGED_EVENT = "sb:subscription-changed";

/** Tell the billing warning that the subscription just changed. */
export function notifySubscriptionChanged() {
  window.dispatchEvent(new Event(CHANGED_EVENT));
}

/**
 * The active workspace's subscription while a payment is overdue
 * (status PAST_DUE), otherwise null.
 */
export function usePastDueSubscription(): Subscription | null {
  const activeOrganizationId =
    useContext(OrganizationContext)?.activeOrganizationId ?? null;
  // Stored with its workspace, so switching never shows a stale warning.
  const [state, setState] = useState<{
    organizationId: string;
    subscription: Subscription | null;
  } | null>(null);

  const refresh = useCallback(() => {
    if (!activeOrganizationId) {
      return;
    }

    getSubscription(activeOrganizationId)
      .then((subscription) =>
        setState({ organizationId: activeOrganizationId, subscription }),
      )
      .catch(() => {
        // No subscription or a network error: nothing to warn about.
        setState({ organizationId: activeOrganizationId, subscription: null });
      });
  }, [activeOrganizationId]);

  useEffect(() => {
    refresh();

    const timer = window.setInterval(refresh, REFRESH_MS);
    window.addEventListener("focus", refresh);
    window.addEventListener(CHANGED_EVENT, refresh);

    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", refresh);
      window.removeEventListener(CHANGED_EVENT, refresh);
    };
  }, [refresh]);

  const subscription =
    state && state.organizationId === activeOrganizationId
      ? state.subscription
      : null;

  return subscription?.status === "PAST_DUE" ? subscription : null;
}
