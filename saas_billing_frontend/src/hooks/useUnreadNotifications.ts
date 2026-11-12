import { useCallback, useContext, useEffect, useState } from "react";

import { getUnreadNotificationCount } from "../api/notifications";
import { OrganizationContext } from "../context/OrganizationContext";

// How often the badge re-checks on its own. Reading or receiving
// notifications also triggers an immediate refresh via the event.
const REFRESH_MS = 60_000;

const CHANGED_EVENT = "sb:notifications-changed";

/** Tell every open badge that notifications just changed. */
export function notifyNotificationsChanged() {
  window.dispatchEvent(new Event(CHANGED_EVENT));
}

/**
 * Unread-notification count for the active workspace, kept fresh:
 * on workspace switch, every minute, when the window regains focus,
 * and whenever notifyNotificationsChanged() fires (mark as read).
 */
export function useUnreadNotifications(): number {
  // Read the context directly: the sidebar also renders in places
  // without a workspace (and in tests), where the badge is just 0.
  const activeOrganizationId =
    useContext(OrganizationContext)?.activeOrganizationId ?? null;
  // The count is stored with the workspace it belongs to, so a
  // workspace switch never shows the previous workspace's number.
  const [state, setState] = useState<{
    organizationId: string;
    count: number;
  } | null>(null);

  const refresh = useCallback(() => {
    if (!activeOrganizationId) {
      return;
    }

    getUnreadNotificationCount(activeOrganizationId)
      .then((count) =>
        setState({ organizationId: activeOrganizationId, count }),
      )
      .catch(() => {
        // Keep the last known count; the badge is not worth an error.
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

  return state && state.organizationId === activeOrganizationId
    ? state.count
    : 0;
}
