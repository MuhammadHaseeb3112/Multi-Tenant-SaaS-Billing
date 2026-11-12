import { act, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithOrg } from "../test/utils";

const api = vi.hoisted(() => ({ getUnreadNotificationCount: vi.fn() }));

vi.mock("../api/notifications", () => api);

import {
  notifyNotificationsChanged,
  useUnreadNotifications,
} from "./useUnreadNotifications";

function Badge() {
  const count = useUnreadNotifications();
  return <span data-testid="count">{count}</span>;
}

describe("useUnreadNotifications", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows the unread count of the active workspace", async () => {
    api.getUnreadNotificationCount.mockResolvedValue(5);

    renderWithOrg(<Badge />, { role: "OWNER" });

    await waitFor(() =>
      expect(screen.getByTestId("count")).toHaveTextContent("5"),
    );
    expect(api.getUnreadNotificationCount).toHaveBeenCalledWith("org-acme");
  });

  it("drops to zero right after notifications are read", async () => {
    api.getUnreadNotificationCount.mockResolvedValueOnce(3);

    renderWithOrg(<Badge />, { role: "OWNER" });

    await waitFor(() =>
      expect(screen.getByTestId("count")).toHaveTextContent("3"),
    );

    api.getUnreadNotificationCount.mockResolvedValueOnce(0);
    act(() => notifyNotificationsChanged());

    await waitFor(() =>
      expect(screen.getByTestId("count")).toHaveTextContent("0"),
    );
  });
});
