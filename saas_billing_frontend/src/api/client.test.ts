import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import apiClient, { refreshAccessToken } from "./client";
import { getAccessToken, setAccessToken } from "./tokenStore";

type Handler = (config: InternalAxiosRequestConfig) => {
  status: number;
  data?: unknown;
};

/** Route apiClient requests to `handler` instead of the network. */
function mockApi(handler: Handler) {
  const seen: InternalAxiosRequestConfig[] = [];

  apiClient.defaults.adapter = async (config) => {
    seen.push(config);
    const { status, data } = handler(config);
    const response = {
      data,
      status,
      statusText: String(status),
      headers: {},
      config,
    };

    if (status >= 400) {
      throw new AxiosError(
        `HTTP ${status}`,
        undefined,
        config,
        undefined,
        response,
      );
    }

    return response;
  };

  return seen;
}

const authHeader = (config: InternalAxiosRequestConfig) =>
  String(config.headers?.Authorization ?? "");

describe("apiClient auth", () => {
  const originalAdapter = apiClient.defaults.adapter;

  beforeEach(() => setAccessToken(null));
  afterEach(() => {
    apiClient.defaults.adapter = originalAdapter;
  });

  it("sends the in-memory access token (never localStorage)", async () => {
    localStorage.setItem("access_token", "stale-local-token");
    setAccessToken("memory-token");
    const seen = mockApi(() => ({ status: 200, data: {} }));

    await apiClient.get("/auth/me/");

    expect(authHeader(seen[0])).toBe("Bearer memory-token");
  });

  it("refreshes once for parallel 401s and retries all of them", async () => {
    setAccessToken("expired");
    const refresh = vi
      .spyOn(axios, "post")
      .mockResolvedValue({ data: { access: "fresh" } });

    const seen = mockApi((config) =>
      authHeader(config) === "Bearer fresh"
        ? { status: 200, data: { url: config.url } }
        : { status: 401 },
    );

    const results = await Promise.all([
      apiClient.get("/invoices/a/"),
      apiClient.get("/invoices/b/"),
      apiClient.get("/invoices/c/"),
    ]);

    // Rotating refresh tokens: a second refresh would use a blacklisted
    // token and log the user out, so there must be exactly one.
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(refresh.mock.calls[0][0]).toContain("/auth/token/refresh/");
    expect(refresh.mock.calls[0][2]).toMatchObject({ withCredentials: true });
    expect(results.map((r) => r.data.url)).toEqual([
      "/invoices/a/",
      "/invoices/b/",
      "/invoices/c/",
    ]);
    expect(getAccessToken()).toBe("fresh");
    expect(seen).toHaveLength(6); // 3 failed + 3 retried
  });

  it("gives up and clears the token when the refresh fails", async () => {
    setAccessToken("expired");
    vi.spyOn(axios, "post").mockRejectedValue(new Error("401"));
    mockApi(() => ({ status: 401 }));

    await expect(apiClient.get("/invoices/")).rejects.toMatchObject({
      response: { status: 401 },
    });
    expect(getAccessToken()).toBeNull();
  });

  it("never tries to refresh for the auth endpoints themselves", async () => {
    const refresh = vi.spyOn(axios, "post");
    mockApi(() => ({ status: 401 }));

    await expect(
      apiClient.post("/auth/login/", { email: "a", password: "b" }),
    ).rejects.toBeTruthy();
    expect(refresh).not.toHaveBeenCalled();
  });

  it("refreshAccessToken stores the new token", async () => {
    vi.spyOn(axios, "post").mockResolvedValue({ data: { access: "t1" } });

    await expect(refreshAccessToken()).resolves.toBe("t1");
    expect(getAccessToken()).toBe("t1");
  });
});
