// Pure dashboard helpers: revenue chart geometry and display values
// (unit-tested in revenueChart.test.ts).

import type { AnalyticsOverview } from "../../api/analytics";
import type { User } from "../../types/auth";

export interface RevenueTrendItem {
  month: string; // "YYYY-MM"
  revenue: string;
}

export interface ChartPoint {
  month: string;
  label: string;
  revenue: number;
  x: number;
  y: number;
}

// SVG drawing area (viewBox 0 0 760 260).
export const CHART = {
  left: 40,
  right: 745,
  top: 35,
  bottom: 205,
  baseline: 220,
} as const;

const monthKey = (date: Date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;

/**
 * One point per month for the last `months` months (oldest first), the
 * current month included. Months without payments are 0, so the line
 * never skips a month.
 */
export function buildRevenueChart(
  trend: RevenueTrendItem[],
  months: number,
  now: Date = new Date(),
): ChartPoint[] {
  const revenueByMonth = new Map(
    trend.map((item) => {
      const value = Number(item.revenue);
      return [item.month, Number.isFinite(value) ? value : 0];
    }),
  );

  const data = Array.from({ length: months }, (_, index) => {
    const date = new Date(
      now.getFullYear(),
      now.getMonth() - (months - 1 - index),
      1,
    );
    const key = monthKey(date);

    return {
      month: key,
      revenue: revenueByMonth.get(key) ?? 0,
      label: date.toLocaleDateString("en-US", { month: "short" }),
    };
  });

  const max = Math.max(...data.map((item) => item.revenue), 0) || 1;

  return data.map((item, index) => ({
    ...item,
    x:
      data.length === 1
        ? (CHART.left + CHART.right) / 2
        : CHART.left +
          (index / (data.length - 1)) * (CHART.right - CHART.left),
    y: CHART.bottom - (item.revenue / max) * (CHART.bottom - CHART.top),
  }));
}

export function linePath(points: ChartPoint[]): string {
  return points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`)
    .join(" ");
}

export function areaPath(points: ChartPoint[]): string {
  if (points.length === 0) return "";

  const first = points[0];
  const last = points[points.length - 1];

  return `${linePath(points)} L ${last.x} ${CHART.baseline} L ${first.x} ${CHART.baseline} Z`;
}

export function greeting(now: Date = new Date()): string {
  const hour = now.getHours();

  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

/** Percentage of the plan limit used, 0-100, for progress bars. */
export function usagePercent(used: number, limit: number): number {
  if (limit <= 0) return 0;
  return Math.min((used / limit) * 100, 100);
}

export function totalPaid(analytics: AnalyticsOverview): number {
  // All-time total from the API; the 12-month trend sum is a fallback
  // for older backends.
  if (analytics.total_paid !== undefined) {
    return Number(analytics.total_paid);
  }

  return analytics.revenue_trend.reduce(
    (total, item) => total + Number(item.revenue || 0),
    0,
  );
}

/**
 * Money the workspace collected from its own customers. Platform
 * subscription fees are not part of it; older backends that do not
 * send the split fall back to the combined total.
 */
export function collectedFromCustomers(
  analytics: AnalyticsOverview,
): number {
  if (analytics.collected_from_customers !== undefined) {
    return Number(analytics.collected_from_customers);
  }

  return totalPaid(analytics);
}

export function initialsOf(user: User | null): string {
  const source = user?.first_name || user?.email || "";
  return source ? source.charAt(0).toUpperCase() : "U";
}
