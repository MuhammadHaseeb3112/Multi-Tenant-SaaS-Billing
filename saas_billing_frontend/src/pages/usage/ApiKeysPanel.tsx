import { useEffect, useState, type FormEvent } from "react";
import {
  AlertCircle,
  Check,
  Copy,
  KeyRound,
  Plus,
  ShieldAlert,
  Trash2,
} from "lucide-react";

import {
  PRODUCT_API_BASE_URL,
  createApiKey,
  listApiKeys,
  revokeApiKey,
  type ApiKey,
  type CreatedApiKey,
} from "../../api/usage";

interface ApiKeysPanelProps {
  organizationId: string;
}

const formatDate = (value: string | null) =>
  value ? new Date(value).toLocaleString() : "Never";

const errorMessage = (err: unknown, fallback: string) => {
  const data = (err as { response?: { data?: Record<string, unknown> } })
    ?.response?.data;

  if (!data) return fallback;
  if (typeof data.detail === "string") return data.detail;

  const first = Object.values(data)[0];
  if (Array.isArray(first) && typeof first[0] === "string") {
    return first[0];
  }

  return fallback;
};

function ApiKeysPanel({ organizationId }: ApiKeysPanelProps) {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [revokingId, setRevokingId] = useState<string | null>(null);
  const [newKey, setNewKey] = useState<CreatedApiKey | null>(null);
  const [copied, setCopied] = useState<"key" | "curl" | null>(null);
  const [error, setError] = useState("");

  const loadKeys = async () => {
    try {
      setError("");
      setKeys(await listApiKeys(organizationId));
    } catch (err) {
      setError(errorMessage(err, "Unable to load API keys."));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    setNewKey(null);
    loadKeys();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [organizationId]);

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault();

    if (!name.trim()) return;

    try {
      setCreating(true);
      setError("");
      const created = await createApiKey(organizationId, name.trim());
      setNewKey(created);
      setName("");
      await loadKeys();
    } catch (err) {
      setError(errorMessage(err, "Unable to create API key."));
    } finally {
      setCreating(false);
    }
  };

  const handleRevoke = async (key: ApiKey) => {
    const confirmed = window.confirm(
      `Revoke "${key.name}"? Apps using this key will stop working immediately.`,
    );

    if (!confirmed) return;

    try {
      setRevokingId(key.id);
      setError("");
      await revokeApiKey(organizationId, key.id);
      if (newKey?.id === key.id) setNewKey(null);
      await loadKeys();
    } catch (err) {
      setError(errorMessage(err, "Unable to revoke API key."));
    } finally {
      setRevokingId(null);
    }
  };

  const copy = async (text: string, what: "key" | "curl") => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(what);
      setTimeout(() => setCopied(null), 2000);
    } catch {
      setError("Copy failed. Select the text and copy it manually.");
    }
  };

  const exampleKey = newKey?.key ?? "sbk_your_key_here";
  const curlExample =
    `curl -X POST ${PRODUCT_API_BASE_URL}/text/analyze/ \\\n` +
    `  -H "Authorization: Api-Key ${exampleKey}" \\\n` +
    `  -H "Content-Type: application/json" \\\n` +
    `  -d '{"text": "Invoices were paid on time."}'`;

  const activeKeys = keys.filter((key) => key.is_active);
  const revokedKeys = keys.filter((key) => !key.is_active);

  return (
    <section className="usage-panel">
      <div className="usage-panel-header">
        <div>
          <h2>API Keys</h2>
          <p>
            Your apps call the Text Insights API with these keys. Every
            successful call is metered against your plan.
          </p>
        </div>
      </div>

      {error && (
        <div className="usage-alert usage-alert-error">
          <AlertCircle size={17} />
          <span>{error}</span>
        </div>
      )}

      {newKey && (
        <div className="apikey-reveal">
          <div className="apikey-reveal-title">
            <ShieldAlert size={18} />
            <strong>Copy your new key now — it won't be shown again.</strong>
          </div>
          <div className="apikey-reveal-row">
            <code>{newKey.key}</code>
            <button
              type="button"
              className="usage-record-btn"
              onClick={() => copy(newKey.key, "key")}
            >
              {copied === "key" ? <Check size={16} /> : <Copy size={16} />}
              {copied === "key" ? "Copied" : "Copy"}
            </button>
          </div>
          <button
            type="button"
            className="apikey-link-btn"
            onClick={() => setNewKey(null)}
          >
            I've saved it
          </button>
        </div>
      )}

      <form className="apikey-create" onSubmit={handleCreate}>
        <input
          type="text"
          value={name}
          maxLength={100}
          placeholder="Key name, e.g. Production server"
          onChange={(event) => setName(event.target.value)}
        />
        <button
          type="submit"
          className="usage-record-btn"
          disabled={creating || !name.trim()}
        >
          <Plus size={16} />
          {creating ? "Creating..." : "Create Key"}
        </button>
      </form>

      {loading ? (
        <p className="apikey-muted">Loading keys...</p>
      ) : keys.length === 0 ? (
        <div className="apikey-empty">
          <KeyRound size={22} />
          <span>No API keys yet. Create one to start calling the API.</span>
        </div>
      ) : (
        <div className="apikey-table-wrap">
          <table className="apikey-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Key</th>
                <th>Requests this period</th>
                <th>Last used</th>
                <th>Created</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {[...activeKeys, ...revokedKeys].map((key) => (
                <tr
                  key={key.id}
                  className={key.is_active ? "" : "apikey-row-revoked"}
                >
                  <td>
                    <strong>{key.name}</strong>
                    {key.created_by_email && (
                      <small>{key.created_by_email}</small>
                    )}
                  </td>
                  <td>
                    <code>{key.prefix}…</code>
                  </td>
                  <td>{key.requests_this_period.toLocaleString()}</td>
                  <td>{formatDate(key.last_used_at)}</td>
                  <td>{formatDate(key.created_at)}</td>
                  <td>
                    <span
                      className={
                        key.is_active
                          ? "apikey-badge apikey-badge-active"
                          : "apikey-badge"
                      }
                    >
                      {key.is_active ? "Active" : "Revoked"}
                    </span>
                  </td>
                  <td>
                    {key.is_active && (
                      <button
                        type="button"
                        className="apikey-revoke-btn"
                        onClick={() => handleRevoke(key)}
                        disabled={revokingId === key.id}
                        title="Revoke key"
                      >
                        <Trash2 size={15} />
                        {revokingId === key.id ? "Revoking..." : "Revoke"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="apikey-quickstart">
        <div className="apikey-quickstart-header">
          <span>Quick start</span>
          <button
            type="button"
            className="apikey-link-btn"
            onClick={() => copy(curlExample, "curl")}
          >
            {copied === "curl" ? "Copied" : "Copy"}
          </button>
        </div>
        <pre>{curlExample}</pre>
      </div>
    </section>
  );
}

export default ApiKeysPanel;
