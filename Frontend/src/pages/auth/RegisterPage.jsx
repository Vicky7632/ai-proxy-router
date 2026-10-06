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
    <main className="grid min-h-screen place-items-center bg-[#f7f8fa] px-4 py-12">
      <div className="w-full max-w-[460px]">
        <Link to="/register" className="mb-9 flex items-center justify-center gap-3">
          <span className="grid h-9 w-9 place-items-center rounded-lg bg-indigo-600 text-xs font-semibold tracking-tight text-white">
            AI
          </span>
          <span className="text-sm font-semibold text-slate-950">
            AI Proxy Router
          </span>
        </Link>
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-[0_8px_30px_-18px_rgba(15,23,42,0.22)] sm:p-9">
          <div className="mb-7">
            <h1 className="text-xl font-semibold tracking-tight text-slate-950">
              Create your account
            </h1>
            <p className="mt-2 text-sm text-slate-500">
              Get started with your AI gateway workspace.
            </p>
          </div>
          <form className="space-y-4" onSubmit={handleSubmit}>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-slate-700">
                  First name
                </span>
                <input
                  name="first_name"
                  autoComplete="given-name"
                  required
                  maxLength={100}
                  value={details.first_name}
                  onChange={updateField}
                  className="h-10 w-full rounded-lg border border-slate-300 px-3 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
                />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-slate-700">
                  Last name
                </span>
                <input
                  name="last_name"
                  autoComplete="family-name"
                  required
                  maxLength={100}
                  value={details.last_name}
                  onChange={updateField}
                  className="h-10 w-full rounded-lg border border-slate-300 px-3 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
                />
              </label>
            </div>
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-slate-700">
                Email address
              </span>
              <input
                type="email"
                name="email"
                autoComplete="email"
                required
                value={details.email}
                onChange={updateField}
                className="h-10 w-full rounded-lg border border-slate-300 px-3 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
                placeholder="you@example.com"
              />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-slate-700">
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
                className="h-10 w-full rounded-lg border border-slate-300 px-3 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
                placeholder="At least 8 characters"
              />
            </label>
            {error && (
              <p role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {error}
              </p>
            )}
            <button
              type="submit"
              disabled={submitting}
              className="mt-1 inline-flex h-10 w-full items-center justify-center rounded-lg bg-indigo-600 px-4 text-sm font-medium text-white shadow-sm transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {submitting ? "Creating account…" : "Create account"}
            </button>
          </form>
          <p className="mt-6 text-center text-sm text-slate-500">
            Already have an account?{" "}
            <Link
              to="/login"
              className="font-medium text-indigo-700 hover:text-indigo-800"
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
