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
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-[0_2px_8px_-5px_rgba(15,23,42,0.16)]">
      <p className="text-[13px] font-medium text-slate-500">{label}</p>
      {loading ? (
        <div className="mt-3 h-8 w-24 animate-pulse rounded-md bg-slate-100" />
      ) : (
        <p className="mt-2 text-[26px] font-semibold tracking-tight text-slate-950">
          {value}
        </p>
      )}
      <p className="mt-2 text-xs text-slate-400">{description}</p>
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
            className="inline-flex h-9 items-center justify-center gap-2 rounded-lg bg-indigo-600 px-3.5 text-sm font-medium text-white shadow-sm transition hover:bg-indigo-700"
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
              onClick={loadAnalytics}
              className="inline-flex h-9 items-center gap-2 rounded-lg bg-indigo-600 px-3 text-sm font-medium text-white hover:bg-indigo-700"
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
            <p className="mt-5 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">
              No request history has been recorded for this API key yet. Send a
              request from the playground to get started.
            </p>
          )}
          {loading && (
            <p className="mt-5 text-center text-sm text-slate-400" role="status">
              Loading live analytics…
            </p>
          )}
        </>
      )}

      <section className="mt-8 rounded-xl border border-slate-200 bg-white p-5 sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-900">
              Your gateway workspace
            </h2>
            <p className="mt-1.5 max-w-xl text-sm leading-6 text-slate-500">
              Create and manage proxy credentials, inspect provider health, or
              send a test completion from the playground.
            </p>
          </div>
          <Link
            to="/dashboard/api-keys"
            className="inline-flex h-9 shrink-0 items-center justify-center gap-2 rounded-lg border border-slate-200 px-3 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
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
