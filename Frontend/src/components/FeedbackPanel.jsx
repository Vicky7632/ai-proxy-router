import Icon from "./Icon";

function FeedbackPanel({ title, description, action, tone = "neutral" }) {
  const styles =
    tone === "error"
      ? "border-rose-900/70 bg-slate-900/80 text-rose-100 shadow-[0_12px_40px_-28px_rgba(0,0,0,0.8)]"
      : "border-slate-800 bg-slate-900/80 text-slate-100 shadow-[0_12px_40px_-28px_rgba(0,0,0,0.8)]";

  return (
    <div className={`rounded-xl border p-7 sm:p-10 ${styles}`}>
      <div className="mx-auto flex max-w-lg flex-col items-center text-center">
        <div
          className={`mb-4 grid h-11 w-11 place-items-center rounded-xl ${
            tone === "error"
              ? "bg-rose-950/60 text-rose-300 ring-1 ring-inset ring-rose-900/70"
              : "bg-indigo-950/70 text-indigo-300 ring-1 ring-inset ring-indigo-800/60"
          }`}
        >
          <Icon name={tone === "error" ? "alert" : "activity"} size={20} />
        </div>
        <h2 className="text-[15px] font-semibold tracking-tight">{title}</h2>
        <p className="mt-2 max-w-md text-[13px] leading-6 text-slate-400">
          {description}
        </p>
        {action && <div className="mt-5">{action}</div>}
      </div>
    </div>
  );
}

export default FeedbackPanel;
