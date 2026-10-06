import { useState } from "react";
import { flushSync } from "react-dom";
import { Link } from "react-router-dom";
import FeedbackPanel from "../../components/FeedbackPanel";
import Icon from "../../components/Icon";
import PageHeader from "../../components/PageHeader";
import { useProxyKey } from "../../context/ProxyKeyContext";
import { getErrorMessage } from "../../services/api";
import { chatService } from "../../services/chat";

function PlaygroundPage() {
  const { proxyKey } = useProxyKey();
  const [model, setModel] = useState("openai/gpt-oss-20b");
  const [prompt, setPrompt] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setResult("");
    try {
      await chatService.stream(
        proxyKey,
        {
          model: model.trim(),
          messages: [{ role: "user", content: prompt.trim() }],
          stream: true,
        },
        (chunk) =>
          flushSync(() => setResult((prev) => prev + chunk)),
      );
    } catch (requestError) {
      setError(getErrorMessage(requestError, "The completion request failed."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Playground"
        description="Send a completion request to your configured provider through the proxy."
      />
      {!proxyKey ? (
        <FeedbackPanel
          title="Connect a proxy API key"
          description="The chat completions endpoint requires a proxy API key. Connect a key before sending a request."
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
      ) : (
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(280px,0.8fr)]">
          <section className="rounded-xl border border-slate-200 bg-white p-5 sm:p-6">
            <form onSubmit={handleSubmit} className="space-y-5">
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-slate-700">
                  Model
                </span>
                <input
                  required
                  value={model}
                  onChange={(event) => setModel(event.target.value)}
                  className="h-10 w-full rounded-lg border border-slate-300 px-3 font-mono text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
                />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-slate-700">
                  Prompt
                </span>
                <textarea
                  required
                  rows={9}
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                  placeholder="What would you like to ask?"
                  className="w-full resize-y rounded-lg border border-slate-300 px-3 py-2.5 text-sm leading-6 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
                />
              </label>
              {error && (
                <p
                  role="alert"
                  className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700"
                >
                  {error}
                </p>
              )}
              <button
                type="submit"
                disabled={submitting || !prompt.trim() || !model.trim()}
                className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
              >
                {submitting ? "Sending request…" : "Send request"}
                {!submitting && <Icon name="arrow" size={15} />}
              </button>
            </form>
          </section>

          <section className="min-h-64 rounded-xl border border-slate-200 bg-white p-5 sm:p-6">
            <h2 className="text-sm font-semibold text-slate-900">Response</h2>
            {submitting && !result ? (
              <div className="mt-5 space-y-2" role="status">
                <div className="h-3 w-4/5 animate-pulse rounded bg-slate-100" />
                <div className="h-3 w-full animate-pulse rounded bg-slate-100" />
                <div className="h-3 w-3/5 animate-pulse rounded bg-slate-100" />
              </div>
            ) : result !== null ? (
              <div className="mt-4">
                <pre className="max-h-[520px] overflow-auto whitespace-pre-wrap break-words rounded-lg bg-slate-950 p-4 font-mono text-xs leading-5 text-slate-100">
                  {result}
                </pre>
              </div>
            ) : (
              <p className="mt-3 text-sm leading-6 text-slate-500">
                The response from your proxy will appear here.
              </p>
            )}
          </section>
        </div>
      )}
    </>
  );
}

export default PlaygroundPage;
