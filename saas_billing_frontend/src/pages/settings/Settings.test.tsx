import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithOrg } from "../../test/utils";

const auth = vi.hoisted(() => ({
  refreshUser: vi.fn(),
  logout: vi.fn(),
}));

const api = vi.hoisted(() => ({
  updateProfile: vi.fn(),
  changePassword: vi.fn(),
}));

vi.mock("../../context/AuthContext", () => ({
  useAuth: () => ({
    user: { first_name: "Sarah", last_name: "Khan", email: "sarah@example.com" },
    logout: auth.logout,
    refreshUser: auth.refreshUser,
  }),
}));

vi.mock("../../api/auth", () => api);

import Settings from "./Settings";

describe("Settings side menu", () => {
  it("highlights and scrolls to the chosen section", () => {
    const scrollIntoView = vi.fn();
    Element.prototype.scrollIntoView = scrollIntoView;

    renderWithOrg(<Settings />, { role: "OWNER" });

    const security = screen.getByRole("button", { name: "Security" });
    expect(screen.getByRole("button", { name: "Profile" })).toHaveClass("active");

    fireEvent.click(security);

    expect(security).toHaveClass("active");
    expect(screen.getByRole("button", { name: "Profile" })).not.toHaveClass("active");
    expect(scrollIntoView).toHaveBeenCalled();
    expect(document.getElementById("security")).not.toBeNull();
  });

  it("has no notification toggles that save nothing", () => {
    renderWithOrg(<Settings />, { role: "OWNER" });

    expect(
      screen.queryByRole("button", { name: "Notifications" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText("Toggle email notifications"),
    ).not.toBeInTheDocument();
  });
});

describe("Settings profile", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("saves the name through the API", async () => {
    api.updateProfile.mockResolvedValue({
      first_name: "Sara",
      last_name: "Khan",
    });

    renderWithOrg(<Settings />, { role: "OWNER" });

    fireEvent.change(screen.getByLabelText("First name"), {
      target: { value: " Sara " },
    });
    fireEvent.click(screen.getByRole("button", { name: /Save Changes/ }));

    await waitFor(() =>
      expect(api.updateProfile).toHaveBeenCalledWith({
        first_name: "Sara",
        last_name: "Khan",
      }),
    );
    expect(await screen.findByText("Saved")).toBeInTheDocument();
    expect(auth.refreshUser).toHaveBeenCalled();
  });

  it("requires a first name and shows server errors", async () => {
    renderWithOrg(<Settings />, { role: "OWNER" });

    fireEvent.change(screen.getByLabelText("First name"), {
      target: { value: "  " },
    });
    fireEvent.click(screen.getByRole("button", { name: /Save Changes/ }));

    expect(
      await screen.findByText("First name is required."),
    ).toBeInTheDocument();
    expect(api.updateProfile).not.toHaveBeenCalled();

    api.updateProfile.mockRejectedValue({
      response: { data: { detail: "Server said no." } },
    });
    fireEvent.change(screen.getByLabelText("First name"), {
      target: { value: "Sara" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Save Changes/ }));

    expect(await screen.findByText("Server said no.")).toBeInTheDocument();
  });
});

describe("Settings change password", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const openForm = () => {
    renderWithOrg(<Settings />, { role: "OWNER" });
    fireEvent.click(screen.getByRole("button", { name: "Change Password" }));
  };

  const fill = (current: string, next: string, confirm: string) => {
    fireEvent.change(screen.getByLabelText("Current password"), {
      target: { value: current },
    });
    fireEvent.change(screen.getByLabelText("New password"), {
      target: { value: next },
    });
    fireEvent.change(screen.getByLabelText("Confirm new password"), {
      target: { value: confirm },
    });
  };

  it("changes the password and confirms it", async () => {
    api.changePassword.mockResolvedValue(
      "Password changed. Other devices have been signed out.",
    );

    openForm();
    fill("OldPass!123", "NewPass!456", "NewPass!456");
    fireEvent.click(screen.getByRole("button", { name: "Update password" }));

    await waitFor(() =>
      expect(api.changePassword).toHaveBeenCalledWith({
        current_password: "OldPass!123",
        new_password: "NewPass!456",
        new_password_confirm: "NewPass!456",
      }),
    );
    expect(
      await screen.findByText(/Other devices have been signed out/),
    ).toBeInTheDocument();
    // The form closes again.
    expect(
      screen.queryByLabelText("Current password"),
    ).not.toBeInTheDocument();
  });

  it("stops mismatched passwords before calling the API", () => {
    openForm();
    fill("OldPass!123", "NewPass!456", "Different!789");
    fireEvent.click(screen.getByRole("button", { name: "Update password" }));

    expect(
      screen.getByText("The two new passwords do not match."),
    ).toBeInTheDocument();
    expect(api.changePassword).not.toHaveBeenCalled();
  });

  it("shows the server reason, e.g. wrong current password", async () => {
    api.changePassword.mockRejectedValue({
      response: {
        data: { current_password: ["Current password is incorrect."] },
      },
    });

    openForm();
    fill("wrong", "NewPass!456", "NewPass!456");
    fireEvent.click(screen.getByRole("button", { name: "Update password" }));

    expect(
      await screen.findByText("Current password is incorrect."),
    ).toBeInTheDocument();
  });
});
