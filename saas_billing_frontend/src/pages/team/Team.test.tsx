import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithOrg } from "../../test/utils";

const api = vi.hoisted(() => ({
  getTeamMembers: vi.fn(),
  inviteTeamMember: vi.fn(),
  getInvitations: vi.fn(),
  resendInvitation: vi.fn(),
  revokeInvitation: vi.fn(),
}));

vi.mock("../../api/tenants", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/tenants")>()),
  getTeamMembers: api.getTeamMembers,
  inviteTeamMember: api.inviteTeamMember,
  getInvitations: api.getInvitations,
  resendInvitation: api.resendInvitation,
  revokeInvitation: api.revokeInvitation,
}));

vi.mock("../../context/AuthContext", () => ({
  useAuth: () => ({ user: { id: "u1", email: "me@example.com" } }),
}));

import Team from "./Team";

const pending = {
  id: "inv1",
  email: "pending@example.com",
  role: "MEMBER",
  status: "PENDING",
  invited_by: "Owner Person",
  created_at: "2026-11-01T00:00:00Z",
  expires_at: "2026-11-08T00:00:00Z",
  accepted_at: null,
};

describe("Team page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getInvitations.mockResolvedValue([]);
  });

  it("members see a message and never call the admin-only API", async () => {
    renderWithOrg(<Team />, { role: "MEMBER" });

    expect(
      await screen.findByText(/Only owners and admins can view and manage/),
    ).toBeInTheDocument();
    expect(api.getTeamMembers).not.toHaveBeenCalled();
    expect(
      screen.queryByRole("button", { name: /Invite Member/ }),
    ).not.toBeInTheDocument();
  });

  it("owners load and see the members", async () => {
    api.getTeamMembers.mockResolvedValue([
      {
        id: "m1",
        user_id: "u2",
        email: "alice@example.com",
        first_name: "Alice",
        last_name: "Doe",
        role: "ACCOUNTANT",
        is_active: true,
        joined_at: "2026-10-01T00:00:00Z",
      },
    ]);

    renderWithOrg(<Team />, { role: "OWNER" });

    expect(await screen.findByText("alice@example.com")).toBeInTheDocument();
    expect(api.getTeamMembers).toHaveBeenCalledWith("org-acme");
    expect(
      screen.getByRole("button", { name: /Invite Member/ }),
    ).toBeInTheDocument();
  });

  it("closes the invite form after a successful invite", async () => {
    api.getTeamMembers.mockResolvedValue([]);
    api.inviteTeamMember.mockResolvedValue({
      message: "Invitation sent successfully.",
    });

    renderWithOrg(<Team />, { role: "OWNER" });

    fireEvent.click(
      await screen.findByRole("button", { name: /Invite Member/ }),
    );
    fireEvent.change(screen.getByPlaceholderText("member@example.com"), {
      target: { value: "new@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Send Invitation/ }));

    expect(
      await screen.findByText(/Invitation sent successfully\. \(new@example\.com\)/),
    ).toBeInTheDocument();
    expect(screen.queryByText("Invite team member")).not.toBeInTheDocument();
  });

  it("lists invitations with their status", async () => {
    api.getTeamMembers.mockResolvedValue([]);
    api.getInvitations.mockResolvedValue([
      pending,
      {
        ...pending,
        id: "inv2",
        email: "joined@example.com",
        status: "ACCEPTED",
        accepted_at: "2026-11-02T00:00:00Z",
      },
    ]);

    renderWithOrg(<Team />, { role: "OWNER" });

    expect(await screen.findByText("pending@example.com")).toBeInTheDocument();
    expect(screen.getByText("joined@example.com")).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument();
    expect(screen.getByText("Accepted")).toBeInTheDocument();
    // Accepted invitations cannot be resent or cancelled.
    expect(screen.getAllByRole("button", { name: "Resend" })).toHaveLength(1);
  });

  it("members never load invitations", async () => {
    renderWithOrg(<Team />, { role: "MEMBER" });

    await screen.findByText(/Only owners and admins/);
    expect(api.getInvitations).not.toHaveBeenCalled();
    expect(screen.queryByText("Invitations")).not.toBeInTheDocument();
  });

  it("resends and cancels an invitation", async () => {
    api.getTeamMembers.mockResolvedValue([]);
    api.getInvitations.mockResolvedValue([pending]);
    api.resendInvitation.mockResolvedValue({});
    api.revokeInvitation.mockResolvedValue(undefined);
    vi.spyOn(window, "confirm").mockReturnValue(true);

    renderWithOrg(<Team />, { role: "OWNER" });

    fireEvent.click(await screen.findByRole("button", { name: "Resend" }));
    expect(
      await screen.findByText("Invitation sent again to pending@example.com."),
    ).toBeInTheDocument();
    expect(api.resendInvitation).toHaveBeenCalledWith("org-acme", "inv1");

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() =>
      expect(screen.queryByText("pending@example.com")).not.toBeInTheDocument(),
    );
    expect(api.revokeInvitation).toHaveBeenCalledWith("org-acme", "inv1");
  });

  it("shows the server reason when the person is already a member", async () => {
    api.getTeamMembers.mockResolvedValue([]);
    api.inviteTeamMember.mockRejectedValue({
      response: {
        data: {
          detail: "alice@example.com is already a member of this organization.",
        },
      },
    });

    renderWithOrg(<Team />, { role: "OWNER" });

    fireEvent.click(
      await screen.findByRole("button", { name: /Invite Member/ }),
    );
    fireEvent.change(screen.getByPlaceholderText("member@example.com"), {
      target: { value: "alice@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Send Invitation/ }));

    expect(
      await screen.findByText(/is already a member of this organization/),
    ).toBeInTheDocument();
  });
});
