import { useMemo, useState } from "react";

import type { AnalyticsOverview } from "../../../api/analytics";
import { areaPath, buildRevenueChart, CHART, linePath } from "../revenueChart";

interface RevenueOverviewProps {
  analytics: AnalyticsOverview | null;
}

const PERIODS = [
  { value: 6, label: "Last 6 months" },
  { value: 12, label: "Last 12 months" },
  { value: 3, label: "Last 3 months" },
];

const GRID_LINES = [35, 90, 145, 200];

export default function RevenueOverview({ analytics }: RevenueOverviewProps) {
  // Was a dropdown with no effect; now it changes the chart period.
  const [months, setMonths] = useState(6);

  const points = useMemo(
    () => buildRevenueChart(analytics?.revenue_trend ?? [], months),
    [analytics, months],
  );

  return (
    <article className="panel">
      <div className="panel-header">
        <div>
          <div className="panel-title">Revenue overview</div>
          <div className="panel-subtitle">Monthly revenue performance</div>
        </div>

        <select
          className="period-select"
          aria-label="Chart period"
          value={months}
          onChange={(event) => setMonths(Number(event.target.value))}
        >
          {PERIODS.map((period) => (
            <option key={period.value} value={period.value}>
              {period.label}
            </option>
          ))}
        </select>
      </div>

      <div className="chart-container">
        <svg
          className="chart-svg"
          viewBox="0 0 760 260"
          preserveAspectRatio="none"
          role="img"
          aria-label="Revenue chart"
        >
          <defs>
            <linearGradient id="revenueGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#818cf8" stopOpacity="0.28" />
              <stop offset="100%" stopColor="#818cf8" stopOpacity="0" />
            </linearGradient>
          </defs>

          {GRID_LINES.map((y) => (
            <line
              key={y}
              className="chart-grid-line"
              x1={CHART.left}
              y1={y}
              x2={CHART.right}
              y2={y}
            />
          ))}

          <path
            className="chart-area"
            d={areaPath(points)}
            fill="url(#revenueGradient)"
          />

          <path
            className="chart-line"
            d={linePath(points)}
            fill="none"
            stroke="#818cf8"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {points.map((point, index) => (
            <circle
              key={`${point.month}-${index}`}
              className="chart-point"
              cx={point.x}
              cy={point.y}
              r="4"
              style={{ animationDelay: `${0.35 + index * 0.08}s` }}
            />
          ))}

          {points.map((point, index) => (
            <text
              key={`label-${point.month}-${index}`}
              className="chart-label"
              x={point.x}
              y="242"
              textAnchor="middle"
            >
              {point.label}
            </text>
          ))}
        </svg>
      </div>
    </article>
  );
}
