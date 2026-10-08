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
              className="inline-flex h-9 items-center gap-2 rounded-lg bg-indigo-500 px-3 text-[13px] font-semibold text-white shadow-sm shadow-indigo-950/40 transition hover:bg-indigo-400"
            >
              Manage API keys
              <Icon name="arrow" size={15} />
            </Link>
          }
        />
      ) : (
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(280px,0.8fr)]">
          <section className="rounded-xl border border-slate-800/90 bg-slate-900/80 p-5 shadow-[0_12px_36px_-28px_rgba(0,0,0,0.9)] sm:p-6">
            <form onSubmit={handleSubmit} className="space-y-5">
              <label className="block">
                <span className="mb-2 block text-[12px] font-semibold tracking-wide text-slate-300">
                  Model
                </span>
                <input
                  required
                  value={model}
                  onChange={(event) => setModel(event.target.value)}
                  className="h-10 w-full rounded-lg border border-slate-700 bg-slate-950/70 px-3 font-mono text-[13px] text-slate-100 shadow-inner shadow-black/20 transition hover:border-slate-600 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                />
              </label>
              <label className="block">
                <span className="mb-2 block text-[12px] font-semibold tracking-wide text-slate-300">
                  Prompt
                </span>
                <textarea
                  required
                  rows={9}
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                  placeholder="What would you like to ask?"
                  className="w-full resize-y rounded-lg border border-slate-700 bg-slate-950/70 px-3 py-2.5 text-[13px] leading-6 text-slate-100 shadow-inner shadow-black/20 transition placeholder:text-slate-500 hover:border-slate-600 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                />
              </label>
              {error && (
                <p
                  role="alert"
                  className="rounded-lg border border-rose-900/70 bg-rose-950/40 px-3 py-2.5 text-[13px] leading-5 text-rose-200"
                >
                  {error}
                </p>
              )}
              <button
                type="submit"
                disabled={submitting || !prompt.trim() || !model.trim()}
                className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-indigo-500 to-violet-500 px-4 text-[13px] font-semibold text-white shadow-sm shadow-indigo-950/40 transition hover:from-indigo-400 hover:to-violet-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
              >
                {submitting ? "Sending request…" : "Send request"}
                {!submitting && <Icon name="arrow" size={15} />}
              </button>
            </form>
          </section>

          <section className="min-h-64 overflow-hidden rounded-xl border border-slate-800/90 bg-slate-900/80 shadow-[0_12px_36px_-28px_rgba(0,0,0,0.9)]">
            <div className="border-b border-slate-800 px-5 py-4 sm:px-6">
              <h2 className="text-[13px] font-semibold tracking-tight text-slate-100">
                Response
              </h2>
            </div>
            {submitting && !result ? (
              <div className="space-y-2 p-5 sm:p-6" role="status">
                <div className="h-3 w-4/5 animate-pulse rounded bg-slate-800" />
                <div className="h-3 w-full animate-pulse rounded bg-slate-800" />
                <div className="h-3 w-3/5 animate-pulse rounded bg-slate-800" />
              </div>
            ) : result !== null ? (
              <div className="p-5 sm:p-6">
                <pre className="max-h-[520px] overflow-auto whitespace-pre-wrap break-words rounded-lg border border-slate-800 bg-slate-950 p-4 font-mono text-[12px] leading-6 text-slate-100 shadow-inner shadow-black/10">
                  {result}
                </pre>
              </div>
            ) : (
              <p className="p-5 text-[13px] leading-6 text-slate-400 sm:p-6">
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
