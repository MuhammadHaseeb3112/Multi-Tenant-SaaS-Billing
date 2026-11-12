import { useEffect } from "react";
import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAuth } from "./AuthContext";
import { AuthProvider } from "./AuthProvider";

const api = vi.hoisted(() => ({
  getMe: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
  register: vi.fn(),
  refreshAccessToken: vi.fn(),
}));

vi.mock("../api/auth", () => ({
  getMe: api.getMe,
  login: api.login,
  logout: api.logout,
  register: api.register,
}));

vi.mock("../api/client", () => ({
  refreshAccessToken: api.refreshAccessToken,
}));

import { getAccessToken, setAccessToken } from "../api/tokenStore";

const me = {
  id: "u1",
  email: "owner@example.com",
  first_name: "Owner",
  last_name: "",
  organizations: [],
};

// The probe reports the latest context value to the test.
const onAuth = vi.fn<(auth: ReturnType<typeof useAuth>) => void>();
const latestAuth = () => onAuth.mock.lastCall![0];

function Probe() {
  const auth = useAuth();

  useEffect(() => {
    onAuth(auth);
  });

  return (
    <div>
      {auth.isLoading ? "loading" : auth.user ? auth.user.email : "anonymous"}
    </div>
  );
}

const renderProvider = () =>
  render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );

describe("AuthProvider", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    onAuth.mockReset();
    setAccessToken(null);
  });

  it("restores the session from the refresh cookie on load", async () => {
    api.refreshAccessToken.mockResolvedValue("access-1");
    api.getMe.mockResolvedValue(me);

    renderProvider();

    expect(screen.getByText("loading")).toBeInTheDocument();
    expect(await screen.findByText(me.email)).toBeInTheDocument();
  });

  it("is anonymous when there is no valid refresh cookie", async () => {
    api.refreshAccessToken.mockResolvedValue(null);

    renderProvider();

    expect(await screen.findByText("anonymous")).toBeInTheDocument();
    expect(api.getMe).not.toHaveBeenCalled();
  });

  it("removes tokens left in localStorage by the old version", async () => {
    localStorage.setItem("access_token", "old");
    localStorage.setItem("refresh_token", "old");
    api.refreshAccessToken.mockResolvedValue(null);

    renderProvider();
    await screen.findByText("anonymous");

    expect(localStorage.getItem("access_token")).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
  });

  it("login keeps the access token in memory only", async () => {
    api.refreshAccessToken.mockResolvedValue(null);
    api.login.mockResolvedValue({
      message: "ok",
      user: me,
      tokens: { access: "access-2" },
    });
    api.getMe.mockResolvedValue(me);

    renderProvider();
    await screen.findByText("anonymous");

    await act(() => latestAuth().login({ email: me.email, password: "x" }));

    expect(await screen.findByText(me.email)).toBeInTheDocument();
    expect(getAccessToken()).toBe("access-2");
    expect(JSON.stringify({ ...localStorage })).not.toContain("access-2");
  });

  it("logout clears the session even if the server call fails", async () => {
    api.refreshAccessToken.mockResolvedValue("access-1");
    api.getMe.mockResolvedValue(me);
    api.logout.mockRejectedValue(new Error("network"));

    renderProvider();
    await screen.findByText(me.email);

    await act(() => latestAuth().logout());

    await waitFor(() =>
      expect(screen.getByText("anonymous")).toBeInTheDocument(),
    );
    expect(getAccessToken()).toBeNull();
  });
});
