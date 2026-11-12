import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithOrg } from "../../test/utils";

const api = vi.hoisted(() => ({
  getUsageSummary: vi.fn(),
  listOverageCharges: vi.fn(),
  listApiKeys: vi.fn(),
}));

vi.mock("../../api/usage", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/usage")>()),
  getUsageSummary: api.getUsageSummary,
  listOverageCharges: api.listOverageCharges,
  listApiKeys: api.listApiKeys,
}));

import Usage from "./Usage";

const summary = {
  resource: "API_REQUEST",
  used: 10400,
  limit: 10000,
  remaining: 0,
  plan: "PRO",
  period_start: "2026-10-26T00:00:00Z",
  period_end: "2026-11-25T00:00:00Z",
  overage_enabled: true,
  overage_requests: 400,
  overage_price_per_1000: "2.00",
  max_overage_requests: 50000,
  estimated_overage_amount: "0.80",
};

describe("Usage page", () => {
  beforeEach(() => {
    api.getUsageSummary.mockResolvedValue(summary);
    api.listOverageCharges.mockResolvedValue([]);
    api.listApiKeys.mockResolvedValue([]);
  });

  it("shows overage for a paid plan over its limit", async () => {
    renderWithOrg(<Usage />);

    expect(
      await screen.findByText(/requests over the limit/),
    ).toHaveTextContent("+400");
    expect(screen.getByText("Now in paid overage")).toBeInTheDocument();
    expect(screen.getByText("Included (PRO)")).toBeInTheDocument();
  });

  it("marks a custom per-organization limit", async () => {
    api.getUsageSummary.mockResolvedValue({
      ...summary,
      limit: 150,
      limit_source: "custom",
      plan_limit: 10000,
    });

    renderWithOrg(<Usage />);

    const badge = await screen.findByText("Custom");
    expect(badge).toHaveAttribute(
      "title",
      expect.stringContaining("plan limit: 10,000"),
    );
  });

  it("owners get the API keys panel and manual adjustment", async () => {
    renderWithOrg(<Usage />, { role: "OWNER" });

    expect(
      await screen.findByPlaceholderText(/Key name/),
    ).toBeInTheDocument();
    expect(screen.getByText("Manual Adjustment")).toBeInTheDocument();
    // The keys panel loads in an effect; on a slow CI runner the input
    // can render before that call is made, so wait for it.
    await waitFor(() =>
      expect(api.listApiKeys).toHaveBeenCalledWith("org-acme"),
    );
  });

  it("members cannot manage keys or record usage", async () => {
    renderWithOrg(<Usage />, { role: "MEMBER" });

    expect(
      await screen.findByText(/Only owners and admins can create or revoke/),
    ).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/Key name/)).not.toBeInTheDocument();
    expect(screen.queryByText("Manual Adjustment")).not.toBeInTheDocument();
    expect(api.listApiKeys).not.toHaveBeenCalled();
  });

  it("shows an error with retry when loading fails", async () => {
    api.getUsageSummary.mockRejectedValue(new Error("down"));

    renderWithOrg(<Usage />);

    expect(await screen.findByText("Usage unavailable")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Try Again/ })).toBeVisible();
  });
});
