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
              className="inline-flex h-9 items-center gap-2 rounded-lg bg-indigo-600 px-3 text-sm font-medium text-white hover:bg-indigo-700"
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
              className="inline-flex h-9 items-center gap-2 rounded-lg bg-indigo-600 px-3 text-sm font-medium text-white hover:bg-indigo-700"
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
              className="h-28 animate-pulse rounded-xl border border-slate-200 bg-white"
            />
          ))}
        </div>
      ) : data ? (
        <>
          <div className="mb-5 rounded-xl border border-indigo-100 bg-indigo-50/60 p-5">
            <p className="text-sm font-medium text-indigo-950">Cache hit rate</p>
            <p className="mt-2 text-3xl font-semibold tracking-tight text-indigo-950">
              {Number(data.cache_hit_rate).toFixed(1)}%
            </p>
            <p className="mt-1 text-xs text-indigo-800">
              {data.cache_hits.toLocaleString()} of{" "}
              {data.total_requests.toLocaleString()} recorded requests served
              from cache
            </p>
          </div>
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
            <div className="border-b border-slate-100 px-5 py-4">
              <h2 className="text-sm font-semibold text-slate-900">
                Request totals
              </h2>
            </div>
            <dl className="grid sm:grid-cols-2 lg:grid-cols-3">
              {fields.map(([key, label]) => (
                <div
                  key={key}
                  className="border-b border-slate-100 px-5 py-4"
                >
                  <dt className="text-xs text-slate-500">{label}</dt>
                  <dd className="mt-1.5 text-lg font-semibold tabular-nums text-slate-900">
                    {Number(data[key]).toLocaleString()}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
          <p className="mt-4 text-xs text-slate-400">
            Values are returned by the existing cache analytics endpoint.
          </p>
        </>
      ) : null}
    </>
  );
}

export default AnalyticsPage;
