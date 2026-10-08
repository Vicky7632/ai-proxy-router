import { Outlet, useLocation } from "react-router-dom";
import { useState } from "react";
import Icon from "../components/Icon";
import Sidebar from "../components/Sidebar";

const pageNames = {
  "/dashboard": "Overview",
  "/dashboard/api-keys": "API keys",
  "/dashboard/playground": "Playground",
  "/dashboard/providers": "Provider health",
  "/dashboard/analytics": "Analytics",
};

function DashboardLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();
  const pageName = pageNames[location.pathname] || "Workspace";

  return (
    <div className="min-h-screen bg-[#080b14] md:flex">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex min-h-screen min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-[68px] items-center gap-3 border-b border-slate-800/80 bg-[#0b1020]/90 px-4 backdrop-blur-md sm:px-7">
          <button
            type="button"
            aria-label="Open navigation"
            onClick={() => setSidebarOpen(true)}
            className="grid h-9 w-9 place-items-center rounded-lg text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-100 md:hidden"
          >
            <Icon name="menu" size={19} />
          </button>
          <div className="flex min-w-0 items-center gap-2 text-sm">
            <span className="hidden text-slate-500 sm:inline">Workspace</span>
            <span className="hidden text-slate-700 sm:inline">/</span>
            <span className="truncate font-medium text-slate-200">{pageName}</span>
          </div>
          <div className="ml-auto inline-flex h-8 items-center gap-2 rounded-full border border-slate-800 bg-slate-900/80 px-3 text-xs font-medium text-slate-300 shadow-sm shadow-black/20">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            <Icon name="lock" size={13} className="text-slate-500" />
            Secure session
          </div>
        </header>
        <main className="w-full flex-1 px-4 py-7 sm:px-7 sm:py-9 lg:px-10">
          <div className="mx-auto w-full max-w-6xl">
            <Outlet />
          </div>
        </main>
        <footer className="border-t border-slate-800/70 px-4 py-4 text-center text-[11px] font-medium tracking-wide text-slate-500 sm:px-7">
          AI Proxy Router <span className="mx-1.5 text-slate-700">·</span>{" "}
          Developer console
        </footer>
      </div>
    </div>
  );
}

export default DashboardLayout;
