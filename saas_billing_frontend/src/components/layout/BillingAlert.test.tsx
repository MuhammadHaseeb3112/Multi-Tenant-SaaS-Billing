import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const getSubscription = vi.fn();
let role = "OWNER";

vi.mock("../../api/billing", () => ({
  getSubscription: (...args: unknown[]) => getSubscription(...args),
}));

vi.mock("../../context/OrganizationContext", async () => {
  const { createContext } = await import("react");

  return {
    OrganizationContext: createContext({
      activeOrganizationId: "org-1",
      get activeOrganization() {
        return { id: "org-1", role };
      },
    }),
  };
});

import BillingAlert from "./BillingAlert";

const subscription = (status: string) => ({
  status,
  plan: { code: "ENTERPRISE", name: "Enterprise" },
  grace_period_end: "2026-11-18T10:00:00Z",
});

const renderAt = (path = "/dashboard") =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <BillingAlert />
    </MemoryRouter>,
  );

describe("BillingAlert", () => {
  beforeEach(() => {
    getSubscription.mockReset();
    role = "OWNER";
  });

  it("warns admins about an overdue payment and the downgrade date", async () => {
    getSubscription.mockResolvedValue(subscription("PAST_DUE"));

    renderAt();

    const alert = await screen.findByRole("alert");

    expect(alert).toHaveTextContent("Payment failed.");
    expect(alert).toHaveTextContent("Enterprise plan");
    expect(alert).toHaveTextContent("Nov 18, 2026");
    expect(alert).toHaveTextContent("moves to the Free plan");
    expect(
      screen.getByRole("button", { name: "Review billing" }),
    ).toBeInTheDocument();
  });

  it("stays hidden while the subscription is healthy", async () => {
    getSubscription.mockResolvedValue(subscription("ACTIVE"));

    renderAt();

    await waitFor(() => expect(getSubscription).toHaveBeenCalled());
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("tells members to ask an admin, without a billing button", async () => {
    role = "MEMBER";
    getSubscription.mockResolvedValue(subscription("PAST_DUE"));

    renderAt();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Ask an owner or admin",
    );
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("drops the button on the subscriptions page itself", async () => {
    getSubscription.mockResolvedValue(subscription("PAST_DUE"));

    renderAt("/subscriptions");

    await screen.findByRole("alert");
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("shows nothing when the subscription cannot be loaded", async () => {
    getSubscription.mockRejectedValue(new Error("offline"));

    renderAt();

    await waitFor(() => expect(getSubscription).toHaveBeenCalled());
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
