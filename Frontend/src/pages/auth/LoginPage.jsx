import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { getErrorMessage } from "../../services/api";

function LoginPage() {
  const { login, status } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const notice = location.state?.notice;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (status === "authenticated") {
    return <Navigate to="/dashboard" replace />;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login({ email: email.trim(), password });
      navigate(location.state?.from?.pathname || "/dashboard", { replace: true });
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Unable to sign in."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-[#080b14] px-4 py-12">
      <div className="w-full max-w-[420px]">
        <Link to="/login" className="mb-8 flex items-center justify-center gap-3">
          <span className="grid h-9 w-9 place-items-center rounded-[10px] bg-gradient-to-br from-indigo-500 to-violet-600 text-[11px] font-bold tracking-tight text-white shadow-sm shadow-indigo-950/40">
            AI
          </span>
          <span className="text-[14px] font-semibold tracking-tight text-slate-100">
            AI Proxy Router
          </span>
        </Link>
        <section className="rounded-xl border border-slate-800 bg-slate-900/90 p-6 shadow-[0_24px_64px_-40px_rgba(0,0,0,0.95)] sm:p-8">
          <div className="mb-7">
            <h1 className="text-[22px] font-semibold tracking-[-0.03em] text-slate-50">
              Welcome back
            </h1>
            <p className="mt-2 text-[13px] leading-5 text-slate-400">
              Sign in to manage your AI gateway.
            </p>
          </div>
          {notice && (
            <p className="mb-5 rounded-lg border border-emerald-900/70 bg-emerald-950/40 px-3 py-2 text-sm text-emerald-200">
              {notice}
            </p>
          )}
          <form className="space-y-5" onSubmit={handleSubmit}>
            <label className="block">
              <span className="mb-2 block text-[12px] font-semibold tracking-wide text-slate-300">
                Email address
              </span>
              <input
                type="email"
                name="email"
                autoComplete="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="h-10 w-full rounded-lg border border-slate-700 bg-slate-950/70 px-3 text-[13px] text-slate-100 shadow-inner shadow-black/20 transition placeholder:text-slate-500 hover:border-slate-600 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                placeholder="you@example.com"
              />
            </label>
            <label className="block">
              <span className="mb-2 block text-[12px] font-semibold tracking-wide text-slate-300">
                Password
              </span>
              <input
                type="password"
                name="password"
                autoComplete="current-password"
                required
                minLength={1}
                maxLength={72}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="h-10 w-full rounded-lg border border-slate-700 bg-slate-950/70 px-3 text-[13px] text-slate-100 shadow-inner shadow-black/20 transition hover:border-slate-600 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                placeholder="Enter your password"
              />
            </label>
            {error && (
              <p role="alert" className="rounded-lg border border-rose-900/70 bg-rose-950/40 px-3 py-2.5 text-[13px] leading-5 text-rose-200">
                {error}
              </p>
            )}
            <button
              type="submit"
              disabled={submitting}
              className="inline-flex h-10 w-full items-center justify-center rounded-lg bg-gradient-to-r from-indigo-500 to-violet-500 px-4 text-[13px] font-semibold text-white shadow-sm shadow-indigo-950/40 transition hover:from-indigo-400 hover:to-violet-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {submitting ? "Signing in…" : "Sign in"}
            </button>
          </form>
          <p className="mt-6 text-center text-[13px] text-slate-400">
            New to AI Proxy Router?{" "}
            <Link
              to="/register"
              className="font-semibold text-indigo-300 transition-colors hover:text-indigo-200"
            >
              Create an account
            </Link>
          </p>
        </section>
        <p className="mt-6 text-center text-[11px] leading-5 text-slate-500">
          Your dashboard session uses HTTP-only cookies.
        </p>
      </div>
    </main>
  );
}

export default LoginPage;
