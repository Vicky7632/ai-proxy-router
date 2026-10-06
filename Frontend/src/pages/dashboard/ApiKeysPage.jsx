import { useCallback, useEffect, useState } from "react";
import FeedbackPanel from "../../components/FeedbackPanel";
import Icon from "../../components/Icon";
import PageHeader from "../../components/PageHeader";
import { useProxyKey } from "../../context/ProxyKeyContext";
import { getErrorMessage } from "../../services/api";
import { apiKeysService } from "../../services/apiKeys";
import { analyticsService } from "../../services/analytics";

function ApiKeysPage() {
  const { proxyKey, setProxyKey } = useProxyKey();
  const [keys, setKeys] = useState([]);
  const [name, setName] = useState("");
  const [existingKey, setExistingKey] = useState("");
  const [createdKey, setCreatedKey] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [copyMessage, setCopyMessage] = useState("");

  const loadKeys = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setKeys(await apiKeysService.list());
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Unable to load API keys."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadKeys();
  }, [loadKeys]);

  async function handleCreate(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setNotice("");
    setCreatedKey("");
    try {
      const created = await apiKeysService.create(name.trim());
      setCreatedKey(created.api_key);
      setProxyKey(created.api_key);
      setName("");
      setNotice("Key created and connected for this browser session.");
      await loadKeys();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Unable to create API key."));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleConnect(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setNotice("");
    try {
      await analyticsService.getCacheAnalytics(existingKey.trim());
      setProxyKey(existingKey.trim());
      setExistingKey("");
      setNotice("API key verified and connected for this browser session.");
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Unable to verify this API key."));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRevoke(id) {
    setError("");
    setNotice("");
    try {
      await apiKeysService.revoke(id);
      setKeys((current) => current.filter((key) => key.id !== id));
      setNotice("API key revoked.");
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Unable to revoke this API key."));
    }
  }

  async function handleCopy() {
    setCopyMessage("");
    try {
      await navigator.clipboard.writeText(createdKey);
      setCopyMessage("Copied to clipboard.");
    } catch {
      setCopyMessage("Copy is unavailable. Select and copy the key manually.");
    }
  }

  return (
    <>
      <PageHeader
        title="API keys"
        description="Manage the credentials used by your applications to access the proxy."
      />

      {error && (
        <div
          role="alert"
          className="mb-5 flex items-start justify-between gap-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800"
        >
          <span>{error}</span>
          <button
            type="button"
            onClick={() => setError("")}
            aria-label="Dismiss error"
            className="text-rose-500 hover:text-rose-800"
          >
            <Icon name="close" size={16} />
          </button>
        </div>
      )}
      {notice && (
        <p
          role="status"
          className="mb-5 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800"
        >
          {notice}
        </p>
      )}

      <section className="mb-6 rounded-xl border border-slate-200 bg-white p-5 sm:p-6">
        <div className="mb-5">
          <h2 className="text-sm font-semibold text-slate-900">Create a key</h2>
          <p className="mt-1 text-sm text-slate-500">
            The secret is shown once. It will be held in memory for this browser
            tab only.
          </p>
        </div>
        <form
          onSubmit={handleCreate}
          className="flex flex-col gap-3 sm:flex-row sm:items-end"
        >
          <label className="block flex-1">
            <span className="mb-1.5 block text-sm font-medium text-slate-700">
              Key name
            </span>
            <input
              required
              maxLength={255}
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="e.g. Development"
              className="h-10 w-full rounded-lg border border-slate-300 px-3 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
            />
          </label>
          <button
            type="submit"
            disabled={submitting || !name.trim()}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-indigo-600 px-3.5 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Icon name="plus" size={16} />
            Create key
          </button>
        </form>
        {createdKey && (
          <div className="mt-5 rounded-lg border border-indigo-200 bg-indigo-50/70 p-4">
            <p className="text-sm font-medium text-indigo-950">
              Save this key now
            </p>
            <p className="mt-1 text-xs leading-5 text-indigo-800">
              It cannot be viewed again. This key is connected to the live
              analytics and proxy tools in this tab.
            </p>
            <div className="mt-3 flex flex-col gap-2 sm:flex-row">
              <code className="min-w-0 flex-1 break-all rounded-md border border-indigo-100 bg-white px-3 py-2 font-mono text-xs leading-5 text-slate-800">
                {createdKey}
              </code>
              <button
                type="button"
                onClick={handleCopy}
                className="inline-flex h-9 shrink-0 items-center justify-center gap-2 rounded-lg border border-indigo-200 bg-white px-3 text-xs font-medium text-indigo-800 hover:bg-indigo-50"
              >
                <Icon name="copy" size={14} />
                Copy
              </button>
            </div>
            {copyMessage && (
              <p role="status" className="mt-2 text-xs text-indigo-800">
                {copyMessage}
              </p>
            )}
          </div>
        )}
      </section>

      <section className="mb-6 rounded-xl border border-slate-200 bg-white p-5 sm:p-6">
        <div className="mb-4">
          <h2 className="text-sm font-semibold text-slate-900">
            Connect an existing key
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Use a proxy key for live analytics, provider health, and Playground.
            It is verified before use and never saved to storage.
          </p>
        </div>
        <form
          onSubmit={handleConnect}
          className="flex flex-col gap-3 sm:flex-row"
        >
          <input
            aria-label="Existing proxy API key"
            type="password"
            autoComplete="off"
            value={existingKey}
            onChange={(event) => setExistingKey(event.target.value)}
            placeholder="sk-…"
            className="h-10 min-w-0 flex-1 rounded-lg border border-slate-300 px-3 font-mono text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
          />
          <button
            type="submit"
            disabled={submitting || !existingKey.trim()}
            className="inline-flex h-10 items-center justify-center rounded-lg border border-slate-300 px-3.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Connect key
          </button>
          {proxyKey && (
            <div className="inline-flex h-10 items-center gap-2">
              <span className="inline-flex items-center gap-2 text-xs text-emerald-700">
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
                Connected in this tab
              </span>
              <button
                type="button"
                onClick={() => {
                  setProxyKey("");
                  setNotice("Proxy key disconnected from this browser tab.");
                }}
                className="text-xs font-medium text-slate-500 underline decoration-slate-300 underline-offset-2 hover:text-slate-800"
              >
                Disconnect
              </button>
            </div>
          )}
        </form>
      </section>

      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <div className="border-b border-slate-100 px-5 py-4 sm:px-6">
          <h2 className="text-sm font-semibold text-slate-900">Your keys</h2>
        </div>
        {loading ? (
          <div className="space-y-3 p-5" role="status" aria-label="Loading API keys">
            <div className="h-10 animate-pulse rounded-md bg-slate-100" />
            <div className="h-10 animate-pulse rounded-md bg-slate-100" />
          </div>
        ) : error && keys.length === 0 ? (
          <FeedbackPanel
            title="API keys couldn’t be loaded"
            description={error}
            tone="error"
            action={
              <button
                type="button"
                onClick={loadKeys}
                className="inline-flex h-9 items-center gap-2 rounded-lg bg-indigo-600 px-3 text-sm font-medium text-white hover:bg-indigo-700"
              >
                <Icon name="refresh" size={15} />
                Try again
              </button>
            }
          />
        ) : keys.length === 0 ? (
          <div className="px-5 py-10 text-center sm:px-6">
            <p className="text-sm font-medium text-slate-700">No API keys yet</p>
            <p className="mt-1 text-sm text-slate-500">
              Create a key to make authenticated requests to your proxy.
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-slate-100">
            {keys.map((key) => (
              <li
                key={key.id}
                className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:px-6"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-slate-800">
                    {key.name || "Unnamed key"}
                  </p>
                  <p className="mt-1 text-xs text-slate-400">
                    Created {new Date(key.created_at).toLocaleDateString()}
                  </p>
                </div>
                <span
                  className={`w-fit rounded-full px-2.5 py-1 text-xs font-medium ${
                    key.revoked_at
                      ? "bg-slate-100 text-slate-500"
                      : "bg-emerald-50 text-emerald-700"
                  }`}
                >
                  {key.revoked_at ? "Revoked" : "Active"}
                </span>
                {!key.revoked_at && (
                  <button
                    type="button"
                    onClick={() => handleRevoke(key.id)}
                    className="h-8 rounded-lg border border-slate-200 px-3 text-xs font-medium text-slate-600 transition hover:border-rose-200 hover:bg-rose-50 hover:text-rose-700"
                  >
                    Revoke
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}

export default ApiKeysPage;
