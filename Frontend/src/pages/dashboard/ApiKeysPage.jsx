import { useCallback, useEffect, useRef, useState } from "react";
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
  const [pendingRevokeKey, setPendingRevokeKey] = useState(null);
  const [revoking, setRevoking] = useState(false);
  const revokeInProgress = useRef(false);

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
    if (revokeInProgress.current) {
      return;
    }
    revokeInProgress.current = true;
    setRevoking(true);
    setError("");
    setNotice("");
    try {
      await apiKeysService.revoke(id);
      setKeys((current) => current.filter((key) => key.id !== id));
      setNotice("API key revoked.");
      setPendingRevokeKey(null);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Unable to revoke this API key."));
    } finally {
      revokeInProgress.current = false;
      setRevoking(false);
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
          className="mb-5 flex items-start justify-between gap-4 rounded-xl border border-rose-900/70 bg-rose-950/40 px-4 py-3.5 text-[13px] leading-5 text-rose-200"
        >
          <span>{error}</span>
          <button
            type="button"
            onClick={() => setError("")}
            aria-label="Dismiss error"
            className="rounded-md p-1 text-rose-400 transition-colors hover:bg-rose-900/50 hover:text-rose-200"
          >
            <Icon name="close" size={16} />
          </button>
        </div>
      )}
      {notice && (
        <p
          role="status"
          className="mb-5 rounded-xl border border-emerald-900/70 bg-emerald-950/35 px-4 py-3.5 text-[13px] leading-5 text-emerald-200"
        >
          {notice}
        </p>
      )}

      <section className="mb-5 rounded-xl border border-slate-800/90 bg-slate-900/80 p-5 shadow-[0_12px_36px_-28px_rgba(0,0,0,0.9)] sm:p-6">
        <div className="mb-5">
          <h2 className="text-[14px] font-semibold tracking-tight text-slate-100">Create a key</h2>
          <p className="mt-1.5 text-[13px] leading-5 text-slate-400">
            The secret is shown once. It will be held in memory for this browser
            tab only.
          </p>
        </div>
        <form
          onSubmit={handleCreate}
          className="flex flex-col gap-3 sm:flex-row sm:items-end"
        >
          <label className="block flex-1">
            <span className="mb-1.5 block text-sm font-medium text-slate-300">
              Key name
            </span>
            <input
              required
              maxLength={255}
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="e.g. Development"
              className="h-10 w-full rounded-lg border border-slate-700 bg-slate-950/70 px-3 text-[13px] text-slate-100 shadow-inner shadow-black/20 transition placeholder:text-slate-500 hover:border-slate-600 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
            />
          </label>
          <button
            type="submit"
            disabled={submitting || !name.trim()}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-indigo-500 to-violet-500 px-3.5 text-[13px] font-semibold text-white shadow-sm shadow-indigo-950/40 transition hover:from-indigo-400 hover:to-violet-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Icon name="plus" size={16} />
            Create key
          </button>
        </form>
        {createdKey && (
          <div className="mt-5 rounded-xl border border-indigo-400/20 bg-indigo-950/35 p-4">
            <p className="text-[13px] font-semibold text-indigo-100">
              Save this key now
            </p>
            <p className="mt-1 text-[12px] leading-5 text-indigo-200/80">
              It cannot be viewed again. This key is connected to the live
              analytics and proxy tools in this tab.
            </p>
            <div className="mt-3 flex flex-col gap-2 sm:flex-row">
              <code className="min-w-0 flex-1 break-all rounded-lg border border-indigo-400/20 bg-slate-950/70 px-3 py-2 font-mono text-[11px] leading-5 text-slate-200">
                {createdKey}
              </code>
              <button
                type="button"
                onClick={handleCopy}
                className="inline-flex h-9 shrink-0 items-center justify-center gap-2 rounded-lg border border-indigo-400/30 bg-indigo-950/50 px-3 text-xs font-medium text-indigo-200 transition hover:bg-indigo-900/50"
              >
                <Icon name="copy" size={14} />
                Copy
              </button>
            </div>
            {copyMessage && (
              <p role="status" className="mt-2 text-xs text-indigo-200">
                {copyMessage}
              </p>
            )}
          </div>
        )}
      </section>

      <section className="mb-5 rounded-xl border border-slate-800/90 bg-slate-900/80 p-5 shadow-[0_12px_36px_-28px_rgba(0,0,0,0.9)] sm:p-6">
        <div className="mb-4">
          <h2 className="text-[14px] font-semibold tracking-tight text-slate-100">
            Connect an existing key
          </h2>
          <p className="mt-1.5 text-[13px] leading-5 text-slate-400">
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
            className="h-10 min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-950/70 px-3 font-mono text-[13px] text-slate-100 shadow-inner shadow-black/20 transition placeholder:text-slate-500 hover:border-slate-600 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
          />
          <button
            type="submit"
            disabled={submitting || !existingKey.trim()}
            className="inline-flex h-10 items-center justify-center rounded-lg border border-slate-700 bg-slate-800/70 px-3.5 text-[13px] font-medium text-slate-200 transition hover:border-slate-600 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Connect key
          </button>
          {proxyKey && (
            <div className="inline-flex h-10 items-center gap-2">
              <span className="inline-flex items-center gap-2 rounded-full bg-emerald-950/50 px-2.5 py-1 text-[11px] font-medium text-emerald-300 ring-1 ring-inset ring-emerald-900/70">
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
                Connected in this tab
              </span>
              <button
                type="button"
                onClick={() => {
                  setProxyKey("");
                  setNotice("Proxy key disconnected from this browser tab.");
                }}
                className="text-xs font-medium text-slate-400 underline decoration-slate-600 underline-offset-2 transition-colors hover:text-slate-100"
              >
                Disconnect
              </button>
            </div>
          )}
        </form>
      </section>

      <section className="overflow-hidden rounded-xl border border-slate-800/90 bg-slate-900/80 shadow-[0_12px_36px_-28px_rgba(0,0,0,0.9)]">
        <div className="border-b border-slate-800 px-5 py-4 sm:px-6">
          <h2 className="text-[14px] font-semibold tracking-tight text-slate-100">Your keys</h2>
        </div>
        {loading ? (
          <div className="space-y-3 p-5" role="status" aria-label="Loading API keys">
            <div className="h-10 animate-pulse rounded-md bg-slate-800" />
            <div className="h-10 animate-pulse rounded-md bg-slate-800" />
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
                className="inline-flex h-9 items-center gap-2 rounded-lg bg-indigo-500 px-3 text-[13px] font-semibold text-white shadow-sm shadow-indigo-950/40 transition hover:bg-indigo-400"
              >
                <Icon name="refresh" size={15} />
                Try again
              </button>
            }
          />
        ) : keys.length === 0 ? (
          <div className="px-5 py-10 text-center sm:px-6">
            <p className="text-[13px] font-semibold text-slate-200">No API keys yet</p>
            <p className="mt-1.5 text-[13px] leading-5 text-slate-400">
              Create a key to make authenticated requests to your proxy.
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-slate-800/80">
            {keys.map((key) => (
              <li
                key={key.id}
                className="flex flex-col gap-3 px-5 py-4 transition-colors hover:bg-slate-800/30 sm:flex-row sm:items-center sm:px-6"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13px] font-semibold text-slate-200">
                    {key.name || "Unnamed key"}
                  </p>
                  <p className="mt-1 text-[11px] text-slate-500">
                    Created {new Date(key.created_at).toLocaleDateString()}
                  </p>
                </div>
                <span
                  className={`w-fit rounded-full px-2.5 py-1 text-xs font-medium ${
                    key.revoked_at
                      ? "bg-slate-800 text-slate-400 ring-1 ring-inset ring-slate-700"
                      : "bg-emerald-950/50 text-emerald-300 ring-1 ring-inset ring-emerald-900/70"
                  }`}
                >
                  {key.revoked_at ? "Revoked" : "Active"}
                </span>
                {!key.revoked_at && (
                  <button
                    type="button"
                    onClick={() => {
                      setError("");
                      setPendingRevokeKey(key);
                    }}
                    className="h-8 rounded-lg border border-slate-700 bg-slate-900 px-3 text-xs font-medium text-slate-300 transition hover:border-rose-800 hover:bg-rose-950/40 hover:text-rose-300"
                  >
                    Revoke
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {pendingRevokeKey && (
        <div
          className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4 backdrop-blur-[3px]"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && !revoking) {
              setPendingRevokeKey(null);
            }
          }}
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="revoke-key-title"
            className="w-full max-w-md rounded-2xl border border-slate-700 bg-slate-900 p-5 shadow-[0_24px_64px_-24px_rgba(0,0,0,0.9)] sm:p-6"
          >
            <h2
              id="revoke-key-title"
              className="text-[16px] font-semibold tracking-tight text-slate-50"
            >
              Revoke API key?
            </h2>
            <p className="mt-2 text-[13px] leading-6 text-slate-300">
              Revoking <strong>{pendingRevokeKey.name || "this key"}</strong> is
              permanent. The key will stop working immediately, and
              applications using it will no longer be able to access the
              proxy.
            </p>
            {error && (
              <p
                role="alert"
                className="mt-3 rounded-lg border border-rose-900/70 bg-rose-950/40 px-3 py-2 text-sm text-rose-200"
              >
                {error}
              </p>
            )}
            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                disabled={revoking}
                onClick={() => setPendingRevokeKey(null)}
                className="h-9 rounded-lg border border-slate-700 bg-slate-800 px-3.5 text-[13px] font-medium text-slate-200 transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={revoking}
                onClick={() => handleRevoke(pendingRevokeKey.id)}
                className="h-9 rounded-lg bg-rose-600 px-3.5 text-[13px] font-semibold text-white shadow-sm shadow-rose-950/40 transition hover:bg-rose-500 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {revoking ? "Revoking…" : "Revoke"}
              </button>
            </div>
          </section>
        </div>
      )}
    </>
  );
}

export default ApiKeysPage;
