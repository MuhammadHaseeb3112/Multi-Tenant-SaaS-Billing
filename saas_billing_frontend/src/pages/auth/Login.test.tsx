import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const auth = vi.hoisted(() => ({ login: vi.fn() }));

vi.mock("../../context/AuthContext", () => ({
  useAuth: () => ({ login: auth.login }),
}));

vi.mock("../../api/tenants", () => ({ previewInvitation: vi.fn() }));
vi.mock("./DemoLogin", () => ({ default: () => null }));

import Login from "./Login";

const submit = () => {
  render(
    <MemoryRouter>
      <Login />
    </MemoryRouter>,
  );

  fireEvent.change(screen.getByLabelText("Email address"), {
    target: { value: "user@example.com" },
  });
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: "SomePass!123" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
};

describe("Login error messages", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("blames the server, not the password, when the server fails", async () => {
    auth.login.mockRejectedValue({ response: { status: 500, data: "" } });

    submit();

    expect(
      await screen.findByText(/The server is not responding/),
    ).toBeInTheDocument();
    expect(screen.queryByText(/credentials/)).not.toBeInTheDocument();
  });

  it("says the same when there is no response at all", async () => {
    auth.login.mockRejectedValue({ response: undefined });

    submit();

    expect(
      await screen.findByText(/The server is not responding/),
    ).toBeInTheDocument();
  });

  it("still shows the server's reason for a wrong password", async () => {
    auth.login.mockRejectedValue({
      response: { status: 401, data: { detail: "Invalid email or password." } },
    });

    submit();

    expect(
      await screen.findByText("Invalid email or password."),
    ).toBeInTheDocument();
  });

  it("still shows the lockout message", async () => {
    auth.login.mockRejectedValue({
      response: {
        status: 429,
        data: { detail: "Too many failed login attempts. Please try again later." },
      },
    });

    submit();

    expect(
      await screen.findByText(/Too many failed login attempts/),
    ).toBeInTheDocument();
  });
});
