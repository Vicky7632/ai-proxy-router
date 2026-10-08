import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import FeedbackPanel from "../../components/FeedbackPanel";
import Icon from "../../components/Icon";
import PageHeader from "../../components/PageHeader";
import { useProxyKey } from "../../context/ProxyKeyContext";
import { getErrorMessage } from "../../services/api";
import { analyticsService } from "../../services/analytics";

const fields = [
  ["total_requests", "Total requests"],
  ["cache_hits", "Cache hits"],
  ["redis_hits", "Redis hits"],
  ["redis_misses", "Redis misses"],
  ["semantic_hits", "Semantic hits"],
  ["semantic_misses", "Semantic misses"],
  ["provider_calls", "Provider calls"],
];

function AnalyticsPage() {
  const { proxyKey } = useProxyKey();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!proxyKey) {
      setData(null);
      return;
    }
    setLoading(true);
    setError("");
    try {
      setData(await analyticsService.getCacheAnalytics(proxyKey));
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Unable to load analytics."));
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
        title="Analytics"
        description="Request and cache activity reported by the proxy analytics API."
      />
      {!proxyKey ? (
        <FeedbackPanel
          title="Connect a proxy API key"
          description="The analytics endpoint is authenticated with a proxy API key. Connect one to view real request and cache counts."
          action={
            <Link
              to="/dashboard/api-keys"
              className="inline-flex h-9 items-center gap-2 rounded-lg bg-indigo-500 px-3 text-[13px] font-semibold text-white shadow-sm shadow-indigo-950/40 transition hover:bg-indigo-400"
            >
              Manage API keys
              <Icon name="arrow" size={15} />
            </Link>
          }
        />
      ) : error ? (
        <FeedbackPanel
          title="Analytics couldn’t be loaded"
          description={error}
          tone="error"
          action={
            <button
              type="button"
              onClick={load}
              className="inline-flex h-9 items-center gap-2 rounded-lg bg-indigo-500 px-3 text-[13px] font-semibold text-white shadow-sm shadow-indigo-950/40 transition hover:bg-indigo-400"
            >
              <Icon name="refresh" size={15} />
              Try again
            </button>
          }
        />
      ) : loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" role="status">
          {fields.slice(0, 6).map(([key]) => (
            <div
              key={key}
              className="h-28 animate-pulse rounded-xl border border-slate-800 bg-slate-900"
            />
          ))}
        </div>
      ) : data ? (
        <>
          <div className="relative mb-5 overflow-hidden rounded-xl border border-indigo-400/20 bg-gradient-to-br from-indigo-950/80 via-slate-900 to-slate-900 p-5 shadow-[0_18px_48px_-36px_rgba(99,102,241,0.55)] sm:p-6">
            <div className="pointer-events-none absolute right-0 top-0 h-36 w-36 rounded-full bg-cyan-400/5 blur-3xl" />
            <p className="relative text-[12px] font-semibold uppercase tracking-[0.1em] text-indigo-300">
              Cache hit rate
            </p>
            <p className="relative mt-2 text-3xl font-semibold tracking-[-0.04em] text-white">
              {Number(data.cache_hit_rate).toFixed(1)}%
            </p>
            <p className="relative mt-1.5 text-[12px] leading-5 text-slate-400">
              {data.cache_hits.toLocaleString()} of{" "}
              {data.total_requests.toLocaleString()} recorded requests served
              from cache
            </p>
          </div>
          <div className="overflow-hidden rounded-xl border border-slate-800/90 bg-slate-900/80 shadow-[0_12px_36px_-28px_rgba(0,0,0,0.9)]">
            <div className="border-b border-slate-800 px-5 py-4 sm:px-6">
              <h2 className="text-[14px] font-semibold tracking-tight text-slate-100">
                Request totals
              </h2>
            </div>
            <dl className="grid sm:grid-cols-2 lg:grid-cols-3">
              {fields.map(([key, label]) => (
                <div
                  key={key}
                  className="border-b border-slate-800/80 px-5 py-4 transition-colors hover:bg-slate-800/40 sm:px-6"
                >
                  <dt className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</dt>
                  <dd className="mt-1.5 text-xl font-semibold tracking-tight tabular-nums text-slate-100">
                    {Number(data[key]).toLocaleString()}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
          <p className="mt-4 text-[11px] text-slate-500">
            Values are returned by the existing cache analytics endpoint.
          </p>
        </>
      ) : null}
    </>
  );
}

export default AnalyticsPage;
