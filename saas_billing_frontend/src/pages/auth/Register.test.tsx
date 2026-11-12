import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithOrg } from "../../test/utils";

const api = vi.hoisted(() => ({
  previewInvitation: vi.fn(),
  acceptInvitation: vi.fn(),
}));

const auth = vi.hoisted(() => ({
  value: {
    register: vi.fn(),
    user: null as null | { email: string },
    isAuthenticated: false,
    isLoading: false,
    logout: vi.fn(),
    refreshUser: vi.fn(),
  },
}));

vi.mock("../../api/tenants", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/tenants")>()),
  previewInvitation: api.previewInvitation,
  acceptInvitation: api.acceptInvitation,
}));

vi.mock("../../context/AuthContext", () => ({
  useAuth: () => auth.value,
}));

import Register from "./Register";

const preview = {
  email: "invited@example.com",
  role: "ACCOUNTANT",
  status: "PENDING",
  invited_by: "Hassan Ali",
  organization_name: "Hassan Labs",
  account_exists: false,
  expires_at: "2026-11-14T00:00:00Z",
};

const route = "/accept-invitation?token=abc123";

describe("Register with an invitation link", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    auth.value.user = null;
    auth.value.isAuthenticated = false;
  });

  it("fills in and locks the invited email", async () => {
    api.previewInvitation.mockResolvedValue(preview);

    renderWithOrg(<Register />, { route });

    expect(
      await screen.findByText("Join Hassan Labs as Accountant"),
    ).toBeInTheDocument();
    const email = screen.getByDisplayValue("invited@example.com");
    expect(email).toHaveAttribute("readonly");
    expect(api.previewInvitation).toHaveBeenCalledWith("abc123");
  });

  it("sends existing accounts to sign in", async () => {
    api.previewInvitation.mockResolvedValue({
      ...preview,
      account_exists: true,
    });

    renderWithOrg(<Register />, { route });

    const link = await screen.findByRole("link", { name: "Sign in to accept" });
    expect(link).toHaveAttribute("href", "/login?invite=abc123");
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument();
  });

  it("explains an expired invitation", async () => {
    api.previewInvitation.mockResolvedValue({ ...preview, status: "EXPIRED" });

    renderWithOrg(<Register />, { route });

    expect(
      await screen.findByText("This invitation has expired."),
    ).toBeInTheDocument();
  });

  it("explains an invalid link", async () => {
    api.previewInvitation.mockRejectedValue(new Error("404"));

    renderWithOrg(<Register />, { route });

    expect(
      await screen.findByText("This invitation link is not valid."),
    ).toBeInTheDocument();
  });

  it("offers a join button to the invited, signed-in user", async () => {
    api.previewInvitation.mockResolvedValue({
      ...preview,
      account_exists: true,
    });
    auth.value.user = { email: "Invited@example.com" };
    auth.value.isAuthenticated = true;

    renderWithOrg(<Register />, { route });

    expect(
      await screen.findByRole("button", { name: "Join Hassan Labs" }),
    ).toBeInTheDocument();
  });

  it("warns when signed in as someone else", async () => {
    api.previewInvitation.mockResolvedValue(preview);
    auth.value.user = { email: "other@example.com" };
    auth.value.isAuthenticated = true;

    renderWithOrg(<Register />, { route });

    expect(await screen.findByText("Different account.")).toBeInTheDocument();
  });
});
