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
    <div className="min-h-screen md:flex">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex min-h-screen min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-[68px] items-center gap-3 border-b border-slate-200 bg-white/95 px-4 backdrop-blur sm:px-7">
          <button
            type="button"
            aria-label="Open navigation"
            onClick={() => setSidebarOpen(true)}
            className="grid h-9 w-9 place-items-center rounded-lg text-slate-500 hover:bg-slate-100 md:hidden"
          >
            <Icon name="menu" size={19} />
          </button>
          <div className="flex min-w-0 items-center gap-2 text-sm">
            <span className="hidden text-slate-400 sm:inline">Workspace</span>
            <span className="hidden text-slate-300 sm:inline">/</span>
            <span className="truncate font-medium text-slate-800">{pageName}</span>
          </div>
          <div className="ml-auto flex items-center gap-2 text-xs text-slate-500">
            <Icon name="lock" size={14} />
            Signed in
          </div>
        </header>
        <main className="w-full flex-1 px-4 py-7 sm:px-7 sm:py-9 lg:px-10">
          <div className="mx-auto w-full max-w-6xl">
            <Outlet />
          </div>
        </main>
        <footer className="border-t border-slate-200/80 px-4 py-4 text-center text-xs text-slate-400 sm:px-7">
          AI Proxy Router <span className="mx-1.5">·</span> Developer console
        </footer>
      </div>
    </div>
  );
}

export default DashboardLayout;
