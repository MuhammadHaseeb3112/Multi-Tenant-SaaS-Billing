import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bell,
  Check,
  CheckCheck,
  RefreshCw,
} from "lucide-react";

import { useOrganization } from "../../context/OrganizationContext";
import { notifyNotificationsChanged } from "../../hooks/useUnreadNotifications";
import {
  getNotifications,
  markAllNotificationsAsRead,
  markNotificationAsRead,
} from "../../api/notifications";

import type { Notification } from "../../api/notifications";

import "./Notifications.css";

const formatDate = (value: string) => {
  const date = new Date(value);

  return date.toLocaleString([], {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
};

const getNotificationIcon = (type: string) => {
  if (type.toLowerCase().includes("invoice")) {
    return "INV";
  }

  if (type.toLowerCase().includes("subscription")) {
    return "SUB";
  }

  if (type.toLowerCase().includes("payment")) {
    return "PAY";
  }

  if (type.toLowerCase().includes("team")) {
    return "TEAM";
  }

  return "SYS";
};

function NotificationsPage() {

  const { activeOrganizationId } = useOrganization();

  const organizationId = activeOrganizationId;

  const [notifications, setNotifications] = useState<
    Notification[]
  >([]);

  const [loading, setLoading] = useState(Boolean(organizationId));
  const [error, setError] = useState("");

  // Fetches and stores data; sets no state before the request, so it can
  // run straight from the mount effect.
  const fetchNotifications = useCallback(async () => {
    if (!organizationId) {
      return;
    }

    await getNotifications(organizationId)
      .then((data) => {
        setNotifications(data);
        setError("");
      })
      .catch((err: unknown) => {
        console.error("Failed to load notifications:", err);
        setError("Failed to load notifications.");
      })
      .finally(() => setLoading(false));
  }, [organizationId]);

  useEffect(() => {
    void fetchNotifications();
  }, [fetchNotifications]);

  // Refresh button.
  const loadNotifications = async () => {
    setLoading(true);
    setError("");

    await fetchNotifications();
  };

  const unreadCount = useMemo(
    () =>
      notifications.filter(
        (notification) => !notification.is_read,
      ).length,
    [notifications],
  );

  const handleMarkRead = async (
    notificationId: string,
  ) => {
    if (!organizationId) {
      return;
    }

    try {
      await markNotificationAsRead(
        organizationId,
        notificationId,
      );

      setNotifications((current) =>
        current.map((notification) =>
          notification.id === notificationId
            ? {
                ...notification,
                is_read: true,
                read_at: new Date().toISOString(),
              }
            : notification,
        ),
      );

      notifyNotificationsChanged();
    } catch (err) {
      console.error(
        "Failed to mark notification as read:",
        err,
      );
    }
  };

  const handleMarkAllRead = async () => {
    if (!organizationId || unreadCount === 0) {
      return;
    }

    try {
      await markAllNotificationsAsRead(
        organizationId,
      );

      setNotifications((current) =>
        current.map((notification) => ({
          ...notification,
          is_read: true,
          read_at:
            notification.read_at ??
            new Date().toISOString(),
        })),
      );

      notifyNotificationsChanged();
    } catch (err) {
      console.error(
        "Failed to mark all notifications as read:",
        err,
      );
    }
  };

  return (
    <main className="notifications-page">
      <div className="notifications-container">
        <header className="notifications-header">
          <div className="notifications-title-group">

            <div>
              <h1>Notifications</h1>
              <p>
                Stay up to date with billing and
                organization activity.
              </p>
            </div>
          </div>

          <div className="notifications-actions">
            <button
              type="button"
              className="notifications-refresh"
              onClick={() => void loadNotifications()}
              disabled={loading}
            >
              <RefreshCw
                size={18}
                className={
                  loading
                    ? "notifications-spin"
                    : ""
                }
              />
              Refresh
            </button>

            <button
              type="button"
              className="notifications-read-all"
              onClick={() => void handleMarkAllRead()}
              disabled={unreadCount === 0}
            >
              <CheckCheck size={18} />
              Mark all read
            </button>
          </div>
        </header>

        <section className="notifications-summary">
          <div className="notifications-summary-icon">
            <Bell size={22} />
          </div>

          <div>
            <strong>
              {unreadCount} unread notification
              {unreadCount === 1 ? "" : "s"}
            </strong>

            <span>
              {notifications.length} total notification
              {notifications.length === 1 ? "" : "s"}
            </span>
          </div>
        </section>

        {error && (
          <div className="notifications-error">
            {error}
          </div>
        )}

        <section className="notifications-list">
          {loading ? (
            <div className="notifications-empty">
              Loading notifications...
            </div>
          ) : notifications.length === 0 ? (
            <div className="notifications-empty">
              <div className="notifications-empty-icon">
                <Bell size={28} />
              </div>

              <h2>No notifications</h2>

              <p>
                You&apos;re all caught up. New billing and
                organization events will appear here.
              </p>
            </div>
          ) : (
            notifications.map((notification) => (
              <article
                key={notification.id}
                className={`notification-item ${
                  !notification.is_read
                    ? "notification-unread"
                    : ""
                }`}
              >
                <div className="notification-icon">
                  {getNotificationIcon(
                    notification.notification_type,
                  )}
                </div>

                <div className="notification-content">
                  <div className="notification-top">
                    <h2>{notification.title}</h2>

                    {!notification.is_read && (
                      <span className="notification-badge">
                        New
                      </span>
                    )}
                  </div>

                  <p>{notification.message}</p>

                  <time>
                    {formatDate(
                      notification.created_at,
                    )}
                  </time>
                </div>

                {!notification.is_read && (
                  <button
                    type="button"
                    className="notification-read-button"
                    onClick={() =>
                      void handleMarkRead(
                        notification.id,
                      )
                    }
                    aria-label="Mark notification as read"
                    title="Mark as read"
                  >
                    <Check size={18} />
                  </button>
                )}
              </article>
            ))
          )}
        </section>
      </div>
    </main>
  );
}

// Remount the page when the active organization changes, so every piece
// of state (loading flags, data, errors) starts fresh for the new org and
// a slow response for the previous org can never overwrite the new one.
export default function Notifications() {
  const { activeOrganizationId } = useOrganization();

  return <NotificationsPage key={activeOrganizationId ?? "none"} />;
}
