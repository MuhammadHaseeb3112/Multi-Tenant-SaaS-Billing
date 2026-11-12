import { describe, expect, it, vi } from "vitest";

import { waitFor } from "./waitFor";

describe("waitFor", () => {
  it("returns as soon as the value is ready", async () => {
    const load = vi
      .fn()
      .mockResolvedValueOnce("PRO")
      .mockResolvedValueOnce("PRO")
      .mockResolvedValueOnce("ENTERPRISE");

    const result = await waitFor(load, (plan) => plan === "ENTERPRISE", {
      delayMs: 1,
    });

    expect(result).toBe("ENTERPRISE");
    expect(load).toHaveBeenCalledTimes(3);
  });

  it("gives up after the last attempt and returns the latest value", async () => {
    const load = vi.fn().mockResolvedValue("PRO");

    const result = await waitFor(load, (plan) => plan === "ENTERPRISE", {
      attempts: 3,
      delayMs: 1,
    });

    expect(result).toBe("PRO");
    expect(load).toHaveBeenCalledTimes(3);
  });

  it("retries after a failed request", async () => {
    const load = vi
      .fn()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce("ENTERPRISE");

    const result = await waitFor(load, (plan) => plan === "ENTERPRISE", {
      delayMs: 1,
    });

    expect(result).toBe("ENTERPRISE");
  });
});
