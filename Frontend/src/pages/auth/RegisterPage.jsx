import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { getErrorMessage } from "../../services/api";
import { authService } from "../../services/auth";

function RegisterPage() {
  const { login, status } = useAuth();
  const navigate = useNavigate();
  const [details, setDetails] = useState({
    first_name: "",
    last_name: "",
    email: "",
    password: "",
  });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (status === "authenticated") {
    return <Navigate to="/dashboard" replace />;
  }

  function updateField(event) {
    setDetails((current) => ({ ...current, [event.target.name]: event.target.value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await authService.register({
        ...details,
        first_name: details.first_name.trim(),
        last_name: details.last_name.trim(),
        email: details.email.trim(),
      });
      try {
        await login({ email: details.email.trim(), password: details.password });
        navigate("/dashboard", { replace: true });
      } catch {
        navigate("/login", {
          replace: true,
          state: { notice: "Your account was created. Sign in to continue." },
        });
      }
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Unable to create your account."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-[#080b14] px-4 py-12">
      <div className="w-full max-w-[460px]">
        <Link to="/register" className="mb-8 flex items-center justify-center gap-3">
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
              Create your account
            </h1>
            <p className="mt-2 text-[13px] leading-5 text-slate-400">
              Get started with your AI gateway workspace.
            </p>
          </div>
          <form className="space-y-4" onSubmit={handleSubmit}>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="mb-2 block text-[12px] font-semibold tracking-wide text-slate-300">
                  First name
                </span>
                <input
                  name="first_name"
                  autoComplete="given-name"
                  required
                  maxLength={100}
                  value={details.first_name}
                  onChange={updateField}
                  className="h-10 w-full rounded-lg border border-slate-700 bg-slate-950/70 px-3 text-[13px] text-slate-100 shadow-inner shadow-black/20 transition hover:border-slate-600 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                />
              </label>
              <label className="block">
                <span className="mb-2 block text-[12px] font-semibold tracking-wide text-slate-300">
                  Last name
                </span>
                <input
                  name="last_name"
                  autoComplete="family-name"
                  required
                  maxLength={100}
                  value={details.last_name}
                  onChange={updateField}
                  className="h-10 w-full rounded-lg border border-slate-700 bg-slate-950/70 px-3 text-[13px] text-slate-100 shadow-inner shadow-black/20 transition hover:border-slate-600 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                />
              </label>
            </div>
            <label className="block">
              <span className="mb-2 block text-[12px] font-semibold tracking-wide text-slate-300">
                Email address
              </span>
              <input
                type="email"
                name="email"
                autoComplete="email"
                required
                value={details.email}
                onChange={updateField}
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
                autoComplete="new-password"
                required
                minLength={8}
                maxLength={72}
                value={details.password}
                onChange={updateField}
                className="h-10 w-full rounded-lg border border-slate-700 bg-slate-950/70 px-3 text-[13px] text-slate-100 shadow-inner shadow-black/20 transition placeholder:text-slate-500 hover:border-slate-600 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                placeholder="At least 8 characters"
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
              className="mt-1 inline-flex h-10 w-full items-center justify-center rounded-lg bg-gradient-to-r from-indigo-500 to-violet-500 px-4 text-[13px] font-semibold text-white shadow-sm shadow-indigo-950/40 transition hover:from-indigo-400 hover:to-violet-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {submitting ? "Creating account…" : "Create account"}
            </button>
          </form>
          <p className="mt-6 text-center text-[13px] text-slate-400">
            Already have an account?{" "}
            <Link
              to="/login"
              className="font-semibold text-indigo-300 transition-colors hover:text-indigo-200"
            >
              Sign in
            </Link>
          </p>
        </section>
      </div>
    </main>
  );
}

export default RegisterPage;
