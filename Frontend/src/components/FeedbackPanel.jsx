import Icon from "./Icon";

function FeedbackPanel({ title, description, action, tone = "neutral" }) {
  const styles =
    tone === "error"
      ? "border-rose-200 bg-rose-50 text-rose-900"
      : "border-slate-200 bg-white text-slate-900";

  return (
    <div className={`rounded-xl border p-6 sm:p-8 ${styles}`}>
      <div className="mx-auto flex max-w-lg flex-col items-center text-center">
        <div
          className={`mb-4 grid h-11 w-11 place-items-center rounded-xl ${
            tone === "error"
              ? "bg-rose-100 text-rose-700"
              : "bg-slate-100 text-slate-600"
          }`}
        >
          <Icon name={tone === "error" ? "alert" : "activity"} size={20} />
        </div>
        <h2 className="text-base font-semibold">{title}</h2>
        <p className="mt-2 text-sm leading-6 text-slate-500">{description}</p>
        {action && <div className="mt-5">{action}</div>}
      </div>
    </div>
  );
}

export default FeedbackPanel;
