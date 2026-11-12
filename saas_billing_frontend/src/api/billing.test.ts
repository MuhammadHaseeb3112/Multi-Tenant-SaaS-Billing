import { afterEach, describe, expect, it } from "vitest";

import apiClient from "./client";
import { openBillingPortal } from "./billing";

const originalAdapter = apiClient.defaults.adapter;

afterEach(() => {
  apiClient.defaults.adapter = originalAdapter;
});

describe("openBillingPortal", () => {
  it("posts to the organization's billing-portal endpoint", async () => {
    let seenUrl = "";
    let seenMethod = "";

    apiClient.defaults.adapter = async (config) => {
      seenUrl = config.url ?? "";
      seenMethod = config.method ?? "";
      return {
        data: { url: "https://billing.stripe.com/p/session/test" },
        status: 201,
        statusText: "Created",
        headers: {},
        config,
      };
    };

    const result = await openBillingPortal("org-123");

    expect(seenMethod).toBe("post");
    expect(seenUrl).toBe("/billing/organizations/org-123/billing-portal/");
    expect(result.url).toBe("https://billing.stripe.com/p/session/test");
  });
});
