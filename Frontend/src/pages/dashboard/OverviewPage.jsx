import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import FeedbackPanel from "../../components/FeedbackPanel";
import Icon from "../../components/Icon";
import PageHeader from "../../components/PageHeader";
import { useAuth } from "../../context/AuthContext";
import { useProxyKey } from "../../context/ProxyKeyContext";
import { getErrorMessage } from "../../services/api";
import { analyticsService } from "../../services/analytics";

const metrics = [
  { key: "total_requests", label: "Total requests", format: (value) => value.toLocaleString() },
  { key: "cache_hit_rate", label: "Cache hit rate", format: (value) => `${Number(value).toFixed(1)}%` },
  { key: "redis_hits", label: "Redis hits", format: (value) => value.toLocaleString() },
  { key: "semantic_hits", label: "Semantic hits", format: (value) => value.toLocaleString() },
  { key: "provider_calls", label: "Provider calls", format: (value) => value.toLocaleString() },
];

function MetricCard({ label, value, description, loading }) {
  return (
    <section className="group rounded-xl border border-slate-800/90 bg-slate-900/80 p-5 shadow-[0_12px_36px_-28px_rgba(0,0,0,0.9)] transition-colors hover:border-slate-700">
      <p className="text-[12px] font-medium tracking-wide text-slate-400">{label}</p>
      {loading ? (
        <div className="mt-3 h-8 w-24 animate-pulse rounded-md bg-slate-800" />
      ) : (
        <p className="mt-2 text-[28px] font-semibold leading-9 tracking-[-0.04em] tabular-nums text-slate-50">
          {value}
        </p>
      )}
      <p className="mt-2 text-[11px] leading-5 text-slate-500">{description}</p>
    </section>
  );
}

function OverviewPage() {
  const { user } = useAuth();
  const { proxyKey } = useProxyKey();
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadAnalytics = useCallback(async () => {
    if (!proxyKey) {
      setAnalytics(null);
      setError("");
      return;
    }
    setLoading(true);
    setError("");
    try {
      setAnalytics(await analyticsService.getCacheAnalytics(proxyKey));
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Unable to load request analytics."));
    } finally {
      setLoading(false);
    }
  }, [proxyKey]);

  useEffect(() => {
    loadAnalytics();
  }, [loadAnalytics]);

  return (
    <>
      <PageHeader
        title="Overview"
        description={`A live view of your AI gateway.${user?.first_name ? ` Welcome, ${user.first_name}.` : ""}`}
        action={
          <Link
            to="/dashboard/playground"
            className="inline-flex h-9 items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-indigo-500 to-violet-500 px-3.5 text-[13px] font-semibold text-white shadow-sm shadow-indigo-950/40 transition hover:from-indigo-400 hover:to-violet-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
          >
            Open playground
            <Icon name="arrow" size={15} />
          </Link>
        }
      />

      {!proxyKey ? (
        <FeedbackPanel
          title="Connect an API key to see live metrics"
          description="Analytics and provider health use your proxy API key, separately from your dashboard sign-in. Connect an existing key or create one to load real usage data."
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
              onClick={loadAnalytics}
              className="inline-flex h-9 items-center gap-2 rounded-lg bg-indigo-500 px-3 text-[13px] font-semibold text-white shadow-sm shadow-indigo-950/40 transition hover:bg-indigo-400"
            >
              <Icon name="refresh" size={15} />
              Try again
            </button>
          }
        />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {metrics.map((metric) => (
              <MetricCard
                key={metric.key}
                label={metric.label}
                loading={loading}
                value={
                  analytics && !loading
                    ? metric.format(analytics[metric.key] ?? 0)
                    : "—"
                }
                description={
                  metric.key === "cache_hit_rate"
                    ? "Share of requests served from cache"
                    : "All-time recorded usage"
                }
              />
            ))}
            <MetricCard
              label="Active providers"
              value="—"
              description="Not reported by the analytics API"
              loading={false}
            />
          </div>
          {!loading && analytics?.total_requests === 0 && (
            <p className="mt-5 rounded-xl border border-slate-800 bg-slate-900/70 px-4 py-3.5 text-[13px] leading-6 text-slate-400">
              No request history has been recorded for this API key yet. Send a
              request from the playground to get started.
            </p>
          )}
          {loading && (
            <p className="mt-5 text-center text-sm text-slate-500" role="status">
              Loading live analytics…
            </p>
          )}
        </>
      )}

      <section className="mt-8 rounded-xl border border-slate-800/90 bg-slate-900/80 p-5 shadow-[0_12px_36px_-28px_rgba(0,0,0,0.9)] sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-[14px] font-semibold tracking-tight text-slate-100">
              Your gateway workspace
            </h2>
            <p className="mt-1.5 max-w-xl text-[13px] leading-6 text-slate-400">
              Create and manage proxy credentials, inspect provider health, or
              send a test completion from the playground.
            </p>
          </div>
          <Link
            to="/dashboard/api-keys"
            className="inline-flex h-9 shrink-0 items-center justify-center gap-2 rounded-lg border border-slate-700 bg-slate-800/70 px-3 text-[13px] font-medium text-slate-200 transition hover:border-slate-600 hover:bg-slate-800"
          >
            View API keys
            <Icon name="arrow" size={15} />
          </Link>
        </div>
      </section>
    </>
  );
}

export default OverviewPage;
