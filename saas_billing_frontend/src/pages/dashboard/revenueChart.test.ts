import { describe, expect, it } from "vitest";

import type { AnalyticsOverview } from "../../api/analytics";
import {
  areaPath,
  buildRevenueChart,
  CHART,
  greeting,
  initialsOf,
  linePath,
  collectedFromCustomers,
  totalPaid,
  usagePercent,
} from "./revenueChart";

const NOW = new Date(2026, 10, 15); // 15 Nov 2026

describe("buildRevenueChart", () => {
  it("returns one point per month, oldest first, ending this month", () => {
    const points = buildRevenueChart([], 6, NOW);

    expect(points.map((p) => p.month)).toEqual([
      "2026-06",
      "2026-07",
      "2026-08",
      "2026-09",
      "2026-10",
      "2026-11",
    ]);
    expect(points.map((p) => p.label)).toEqual([
      "Jun",
      "Jul",
      "Aug",
      "Sep",
      "Oct",
      "Nov",
    ]);
  });

  it("crosses the year boundary", () => {
    const points = buildRevenueChart([], 12, NOW);

    expect(points[0].month).toBe("2025-12");
    expect(points).toHaveLength(12);
  });

  it("fills months without payments with 0 and ignores bad values", () => {
    const points = buildRevenueChart(
      [
        { month: "2026-10", revenue: "29.00" },
        { month: "2026-11", revenue: "not-a-number" },
      ],
      3,
      NOW,
    );

    expect(points.map((p) => p.revenue)).toEqual([0, 29, 0]);
  });

  it("scales the highest month to the top and zero to the bottom", () => {
    const points = buildRevenueChart(
      [
        { month: "2026-10", revenue: "50" },
        { month: "2026-11", revenue: "100" },
      ],
      3,
      NOW,
    );

    expect(points[0].y).toBe(CHART.bottom);
    expect(points[1].y).toBe((CHART.top + CHART.bottom) / 2);
    expect(points[2].y).toBe(CHART.top);
    expect(points[0].x).toBe(CHART.left);
    expect(points[2].x).toBe(CHART.right);
  });

  it("keeps a flat line at the bottom when there is no revenue", () => {
    const points = buildRevenueChart([], 3, NOW);

    expect(points.every((p) => p.y === CHART.bottom)).toBe(true);
  });
});

describe("chart paths", () => {
  it("draws a line through every point and closes the area", () => {
    const points = buildRevenueChart([], 3, NOW);

    expect(linePath(points)).toMatch(/^M \S+ \S+ L \S+ \S+ L \S+ \S+$/);
    expect(areaPath(points)).toMatch(/ Z$/);
    expect(areaPath([])).toBe("");
  });
});

describe("display helpers", () => {
  it("greets by time of day", () => {
    expect(greeting(new Date(2026, 0, 1, 9))).toBe("Good morning");
    expect(greeting(new Date(2026, 0, 1, 14))).toBe("Good afternoon");
    expect(greeting(new Date(2026, 0, 1, 20))).toBe("Good evening");
  });

  it("caps usage at 100% and handles a zero limit", () => {
    expect(usagePercent(50, 200)).toBe(25);
    expect(usagePercent(10400, 10000)).toBe(100);
    expect(usagePercent(5, 0)).toBe(0);
  });

  it("uses the API total_paid, else sums the trend", () => {
    const base = {
      revenue_trend: [
        { month: "2026-10", revenue: "10.00" },
        { month: "2026-11", revenue: "5.50" },
      ],
    } as AnalyticsOverview;

    expect(totalPaid({ ...base, total_paid: "99.00" })).toBe(99);
    expect(totalPaid(base)).toBe(15.5);
  });

  it("keeps platform fees out of the customer total", () => {
    const base = {
      revenue_trend: [],
      total_paid: "2459.00",
    } as unknown as AnalyticsOverview;

    expect(
      collectedFromCustomers({
        ...base,
        collected_from_customers: "2430.00",
      }),
    ).toBe(2430);

    // Older backend without the split: fall back to the total.
    expect(collectedFromCustomers(base)).toBe(2459);
  });

  it("builds avatar initials", () => {
    const user = {
      id: "1",
      email: "zoe@example.com",
      first_name: "",
      last_name: "",
      organizations: [],
    };

    expect(initialsOf({ ...user, first_name: "shah" })).toBe("S");
    expect(initialsOf(user)).toBe("Z");
    expect(initialsOf(null)).toBe("U");
  });
});
