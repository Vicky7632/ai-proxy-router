function PageHeader({ title, description, action }) {
  return (
    <div className="mb-8 flex flex-col gap-5 border-b border-slate-800/80 pb-6 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-[26px] font-semibold tracking-[-0.035em] text-slate-50 sm:text-[28px]">
          {title}
        </h1>
        {description && (
          <p className="mt-2 max-w-2xl text-[13px] leading-6 text-slate-400">
            {description}
          </p>
        )}
      </div>
      {action && <div className="flex shrink-0 items-center">{action}</div>}
    </div>
  );
}

export default PageHeader;
