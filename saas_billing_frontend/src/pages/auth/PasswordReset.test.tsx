import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  requestPasswordReset: vi.fn(),
  validatePasswordResetLink: vi.fn(),
  confirmPasswordReset: vi.fn(),
}));

vi.mock("../../api/auth", () => api);

import ForgotPassword from "./ForgotPassword";
import ResetPassword from "./ResetPassword";

const renderAt = (ui: React.ReactElement, path = "/") =>
  render(<MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>);

describe("Forgot password page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("sends a reset link and confirms it", async () => {
    api.requestPasswordReset.mockResolvedValue(
      "If an account exists for that email, a password reset link has been sent.",
    );

    renderAt(<ForgotPassword />);

    fireEvent.change(screen.getByLabelText("Email address"), {
      target: { value: " user@example.com " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send reset link" }));

    expect(await screen.findByText("Check your inbox")).toBeInTheDocument();
    expect(api.requestPasswordReset).toHaveBeenCalledWith("user@example.com");
    expect(
      screen.queryByRole("button", { name: "Send reset link" }),
    ).not.toBeInTheDocument();
  });

  it("asks for an email first", () => {
    renderAt(<ForgotPassword />);

    fireEvent.click(screen.getByRole("button", { name: "Send reset link" }));

    expect(
      screen.getByText("Please enter your email address."),
    ).toBeInTheDocument();
    expect(api.requestPasswordReset).not.toHaveBeenCalled();
  });
});

describe("Reset password page", () => {
  const link = "/reset-password?uid=abc&token=tok-123";

  beforeEach(() => {
    vi.clearAllMocks();
  });

  const fill = (password: string, confirm: string) => {
    fireEvent.change(screen.getByLabelText("New password"), {
      target: { value: password },
    });
    fireEvent.change(screen.getByLabelText("Confirm new password"), {
      target: { value: confirm },
    });
  };

  it("sets a new password from a valid link", async () => {
    api.validatePasswordResetLink.mockResolvedValue(undefined);
    api.confirmPasswordReset.mockResolvedValue(
      "Your password has been reset. You can now sign in.",
    );

    renderAt(<ResetPassword />, link);

    await screen.findByLabelText("New password");
    expect(api.validatePasswordResetLink).toHaveBeenCalledWith("abc", "tok-123");

    fill("NewPass!456", "NewPass!456");
    fireEvent.click(screen.getByRole("button", { name: "Set new password" }));

    expect(await screen.findByText("Password updated")).toBeInTheDocument();
    expect(api.confirmPasswordReset).toHaveBeenCalledWith({
      uid: "abc",
      token: "tok-123",
      new_password: "NewPass!456",
      new_password_confirm: "NewPass!456",
    });
    expect(
      screen.getByRole("link", { name: "Go to sign in" }),
    ).toHaveAttribute("href", "/login");
  });

  it("explains an expired or used link", async () => {
    api.validatePasswordResetLink.mockRejectedValue({
      response: {
        data: {
          detail:
            "This password reset link is invalid or has expired. Please request a new one.",
        },
      },
    });

    renderAt(<ResetPassword />, link);

    expect(
      await screen.findByText(/invalid or has expired/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Request a new link" }),
    ).toHaveAttribute("href", "/forgot-password");
    expect(screen.queryByLabelText("New password")).not.toBeInTheDocument();
  });

  it("treats a link without uid or token as invalid", () => {
    renderAt(<ResetPassword />, "/reset-password");

    expect(screen.getByText(/invalid or has expired/)).toBeInTheDocument();
    expect(api.validatePasswordResetLink).not.toHaveBeenCalled();
  });

  it("checks the passwords match and shows server errors", async () => {
    api.validatePasswordResetLink.mockResolvedValue(undefined);
    api.confirmPasswordReset.mockRejectedValue({
      response: { data: { new_password: ["This password is too common."] } },
    });

    renderAt(<ResetPassword />, link);
    await screen.findByLabelText("New password");

    fill("NewPass!456", "Other!789");
    fireEvent.click(screen.getByRole("button", { name: "Set new password" }));
    expect(
      screen.getByText("The two passwords do not match."),
    ).toBeInTheDocument();
    expect(api.confirmPasswordReset).not.toHaveBeenCalled();

    fill("password1", "password1");
    fireEvent.click(screen.getByRole("button", { name: "Set new password" }));
    await waitFor(() =>
      expect(
        screen.getByText("This password is too common."),
      ).toBeInTheDocument(),
    );
  });
});
