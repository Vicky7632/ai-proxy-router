import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import FeedbackPanel from "../../components/FeedbackPanel";
import Icon from "../../components/Icon";
import PageHeader from "../../components/PageHeader";
import { useProxyKey } from "../../context/ProxyKeyContext";
import { getErrorMessage } from "../../services/api";
import { providersService } from "../../services/providers";

function formatTimestamp(value) {
  return value ? new Date(value).toLocaleString() : "Not recorded";
}

function ProvidersPage() {
  const { proxyKey } = useProxyKey();
  const [providers, setProviders] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!proxyKey) {
      setProviders(null);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const result = await providersService.getHealth(proxyKey);
      setProviders(result.providers);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Unable to load provider health."));
    } finally {
      setLoading(false);
    }
  }, [proxyKey]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <>
      <PageHeader
        title="Provider health"
        description="Request and failure counters reported for configured providers."
        action={
          proxyKey && (
            <button
              type="button"
              onClick={load}
              disabled={loading}
              className="inline-flex h-9 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              <Icon name="refresh" size={15} />
              Refresh
            </button>
          )
        }
      />
      {!proxyKey ? (
        <FeedbackPanel
          title="Connect a proxy API key"
          description="Provider health is returned by an endpoint authenticated with a proxy API key. Connect one to view actual provider counters."
          action={
            <Link
              to="/dashboard/api-keys"
              className="inline-flex h-9 items-center gap-2 rounded-lg bg-indigo-600 px-3 text-sm font-medium text-white hover:bg-indigo-700"
            >
              Manage API keys
              <Icon name="arrow" size={15} />
            </Link>
          }
        />
      ) : error ? (
        <FeedbackPanel
          title="Provider health couldn’t be loaded"
          description={error}
          tone="error"
          action={
            <button
              type="button"
              onClick={load}
              className="inline-flex h-9 items-center gap-2 rounded-lg bg-indigo-600 px-3 text-sm font-medium text-white hover:bg-indigo-700"
            >
              <Icon name="refresh" size={15} />
              Try again
            </button>
          }
        />
      ) : loading ? (
        <div className="grid gap-4 md:grid-cols-2" role="status">
          {[1, 2, 3].map((item) => (
            <div
              key={item}
              className="h-44 animate-pulse rounded-xl border border-slate-200 bg-white"
            />
          ))}
        </div>
      ) : providers ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Object.entries(providers).map(([name, health]) => (
            <section
              key={name}
              className="rounded-xl border border-slate-200 bg-white p-5"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-sm font-semibold capitalize text-slate-900">
                    {name}
                  </h2>
                  <p className="mt-1 text-xs text-slate-400">
                    Health counters
                  </p>
                </div>
                <span
                  className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                    health.consecutive_failures > 0
                      ? "bg-amber-50 text-amber-700"
                      : "bg-slate-100 text-slate-600"
                  }`}
                >
                  {health.consecutive_failures > 0
                    ? "Failures observed"
                    : "No consecutive failures"}
                </span>
              </div>
              <dl className="mt-5 grid grid-cols-2 gap-y-4">
                <div>
                  <dt className="text-xs text-slate-500">Requests</dt>
                  <dd className="mt-1 text-sm font-semibold tabular-nums text-slate-800">
                    {health.total_requests.toLocaleString()}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-500">Failures</dt>
                  <dd className="mt-1 text-sm font-semibold tabular-nums text-slate-800">
                    {health.total_failures.toLocaleString()}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-500">Last success</dt>
                  <dd className="mt-1 text-xs text-slate-700">
                    {formatTimestamp(health.last_success_at)}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-500">Last failure</dt>
                  <dd className="mt-1 text-xs text-slate-700">
                    {formatTimestamp(health.last_failure_at)}
                  </dd>
                </div>
              </dl>
            </section>
          ))}
        </div>
      ) : null}
      {providers && Object.keys(providers).length === 0 && !loading && (
        <FeedbackPanel
          title="No provider health data yet"
          description="The API returned no provider records. Health data will appear after the backend records provider requests."
        />
      )}
      <p className="mt-5 text-xs text-slate-400">
        The health API provides counters, not an availability guarantee.
      </p>
    </>
  );
}

export default ProvidersPage;
