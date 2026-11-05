import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Search, RefreshCw } from "lucide-react";

import { useOrganization } from "../../context/OrganizationContext";
import { getAuditLogs } from "../../api/audit";
import type { AuditLog } from "../../api/audit";

function AuditPage() {
  const navigate = useNavigate();
  const { activeOrganizationId } = useOrganization();
  const organizationId = activeOrganizationId;


  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(Boolean(organizationId));
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");

  // Fetches and stores data; sets no state before the request, so it can
  // run straight from the mount effect.
  const fetchLogs = useCallback(async () => {
    if (!organizationId) {
      return;
    }

    await getAuditLogs(organizationId)
      .then((data) => {
        setLogs(data);
        setError("");
      })
      .catch((err: unknown) => {
        console.error("Failed to load audit logs:", err);
        setError("Failed to load activity.");
      })
      .finally(() => setLoading(false));
  }, [organizationId]);

  useEffect(() => {
    void fetchLogs();
  }, [fetchLogs]);

  // Refresh button.
  const loadLogs = () => {
    setLoading(true);
    setError("");
    void fetchLogs();
  };

  const filteredLogs = useMemo(() => {
    const query = search.trim().toLowerCase();

    if (!query) {
      return logs;
    }

    return logs.filter((log) =>
      [
        log.action,
        log.resource_type,
        log.description,
        log.user_email,
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(query)),
    );
  }, [logs, search]);

  return (
    <div className="audit-page">
      <style>{`
        .audit-page {
          min-height: 100vh;
          background: #f8fafc;
          padding: 32px;
          color: #0f172a;
        }

        .audit-container {
          max-width: 1400px;
          margin: 0 auto;
        }

        .audit-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 20px;
          margin-bottom: 28px;
        }

        .audit-title-row {
          display: flex;
          align-items: center;
          gap: 14px;
        }

        .audit-back {
          width: 42px;
          height: 42px;
          border: 1px solid #e2e8f0;
          background: white;
          border-radius: 10px;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          color: #475569;
        }

        .audit-back:hover {
          background: #f1f5f9;
        }

        .audit-title {
          margin: 0;
          font-size: 28px;
          font-weight: 700;
        }

        .audit-subtitle {
          margin: 5px 0 0;
          color: #64748b;
          font-size: 14px;
        }

        .audit-actions {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .audit-search {
          width: 280px;
          height: 42px;
          border: 1px solid #e2e8f0;
          border-radius: 10px;
          background: white;
          padding: 0 14px 0 40px;
          outline: none;
          font-size: 14px;
        }

        .audit-search:focus {
          border-color: #6366f1;
        }

        .search-wrapper {
          position: relative;
        }

        .search-icon {
          position: absolute;
          left: 13px;
          top: 50%;
          transform: translateY(-50%);
          color: #94a3b8;
        }

        .refresh-button {
          height: 42px;
          padding: 0 14px;
          border: 1px solid #e2e8f0;
          border-radius: 10px;
          background: white;
          display: flex;
          align-items: center;
          gap: 8px;
          cursor: pointer;
          color: #475569;
          font-weight: 500;
        }

        .refresh-button:hover {
          background: #f1f5f9;
        }

        .audit-card {
          background: white;
          border: 1px solid #e2e8f0;
          border-radius: 14px;
          overflow: hidden;
        }

        .audit-table-wrapper {
          overflow-x: auto;
        }

        .audit-table {
          width: 100%;
          border-collapse: collapse;
        }

        .audit-table th {
          text-align: left;
          padding: 15px 20px;
          background: #f8fafc;
          border-bottom: 1px solid #e2e8f0;
          color: #64748b;
          font-size: 12px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }

        .audit-table td {
          padding: 17px 20px;
          border-bottom: 1px solid #f1f5f9;
          font-size: 14px;
          vertical-align: top;
        }

        .audit-table tr:last-child td {
          border-bottom: none;
        }

        .action-badge {
          display: inline-flex;
          padding: 5px 9px;
          border-radius: 7px;
          background: #eef2ff;
          color: #4f46e5;
          font-size: 12px;
          font-weight: 700;
        }

        .resource {
          color: #475569;
        }

        .description {
          color: #334155;
          max-width: 500px;
        }

        .user-email {
          color: #64748b;
        }

        .date {
          color: #64748b;
          white-space: nowrap;
        }

        .audit-empty,
        .audit-loading,
        .audit-error {
          padding: 50px 20px;
          text-align: center;
          color: #64748b;
        }

        .audit-error {
          color: #dc2626;
        }

        @media (max-width: 800px) {
          .audit-page {
            padding: 20px;
          }

          .audit-header {
            align-items: flex-start;
            flex-direction: column;
          }

          .audit-actions {
            width: 100%;
          }

          .search-wrapper {
            flex: 1;
          }

          .audit-search {
            width: 100%;
          }
        }
      `}</style>

      <div className="audit-container">
        <div className="audit-header">
          <div className="audit-title-row">
            <button
              className="audit-back"
              onClick={() => navigate("/dashboard")}
              title="Back to Dashboard"
            >
              <ArrowLeft size={19} />
            </button>

            <div>
              <h1 className="audit-title">Recent Activity</h1>
              <p className="audit-subtitle">
                View activity and changes made in your organization.
              </p>
            </div>
          </div>

          <div className="audit-actions">
            <div className="search-wrapper">
              <Search size={17} className="search-icon" />

              <input
                className="audit-search"
                type="text"
                placeholder="Search activity..."
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </div>

            <button
              className="refresh-button"
              onClick={loadLogs}
              disabled={loading}
            >
              <RefreshCw size={16} />
              Refresh
            </button>
          </div>
        </div>

        <div className="audit-card">
          {loading ? (
            <div className="audit-loading">
              Loading activity...
            </div>
          ) : error ? (
            <div className="audit-error">{error}</div>
          ) : filteredLogs.length === 0 ? (
            <div className="audit-empty">
              No activity found.
            </div>
          ) : (
            <div className="audit-table-wrapper">
              <table className="audit-table">
                <thead>
                  <tr>
                    <th>Action</th>
                    <th>Resource</th>
                    <th>Description</th>
                    <th>User</th>
                    <th>Date</th>
                  </tr>
                </thead>

                <tbody>
                  {filteredLogs.map((log) => (
                    <tr key={log.id}>
                      <td>
                        <span className="action-badge">
                          {log.action}
                        </span>
                      </td>

                      <td className="resource">
                        {log.resource_type}
                      </td>

                      <td className="description">
                        {log.description}
                      </td>

                      <td className="user-email">
                        {log.user_email || "System"}
                      </td>

                      <td className="date">
                        {new Date(log.created_at).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Remount the page when the active organization changes, so every piece
// of state (loading flags, data, errors) starts fresh for the new org and
// a slow response for the previous org can never overwrite the new one.
function Audit() {
  const { activeOrganizationId } = useOrganization();

  return <AuditPage key={activeOrganizationId ?? "none"} />;
}

export default Audit;