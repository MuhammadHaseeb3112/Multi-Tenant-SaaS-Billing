import { useNavigate } from "react-router-dom";

import type { AuditLog } from "../../../api/audit";
import { IconArrowRight } from "../icons";

interface RecentActivityProps {
  activity: AuditLog[];
  limit?: number;
}

const emptyStyle = { padding: "20px 0", color: "#64748b", fontSize: "11px" };

export default function RecentActivity({
  activity,
  limit = 3,
}: RecentActivityProps) {
  const navigate = useNavigate();

  return (
    <article className="panel">
      <div className="panel-header">
        <div>
          <div className="panel-title">Recent activity</div>
          <div className="panel-subtitle">Latest account events</div>
        </div>

        <button
          type="button"
          className="view-all"
          onClick={() => navigate("/audit")}
        >
          View all
          <IconArrowRight size={16} />
        </button>
      </div>

      <div className="activity-list">
        {activity.slice(0, limit).map((item) => (
          <div className="activity-item" key={item.id}>
            <div className="activity-dot" />

            <div className="activity-content">
              <div className="activity-title">
                {item.description || item.action}
              </div>
              <div className="activity-time">
                {new Date(item.created_at).toLocaleString("en-US", {
                  month: "short",
                  day: "numeric",
                  hour: "numeric",
                  minute: "2-digit",
                })}
              </div>
            </div>
          </div>
        ))}

        {activity.length === 0 && (
          <div style={emptyStyle}>No recent activity.</div>
        )}
      </div>
    </article>
  );
}
