import { NavLink, useNavigate } from "react-router-dom";
import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useProxyKey } from "../context/ProxyKeyContext";
import Icon from "./Icon";
import { getErrorMessage } from "../services/api";

const links = [
  { label: "Overview", to: "/dashboard", icon: "overview", end: true },
  { label: "API keys", to: "/dashboard/api-keys", icon: "key" },
  { label: "Playground", to: "/dashboard/playground", icon: "playground" },
  { label: "Provider health", to: "/dashboard/providers", icon: "providers" },
  { label: "Analytics", to: "/dashboard/analytics", icon: "analytics" },
];

function Sidebar({ open, onClose }) {
  const { user, logout } = useAuth();
  const { setProxyKey } = useProxyKey();
  const navigate = useNavigate();
  const fullName = [user?.first_name, user?.last_name].filter(Boolean).join(" ");
  const [logoutError, setLogoutError] = useState("");

  async function handleLogout() {
    setLogoutError("");
    try {
      await logout();
      setProxyKey("");
      onClose();
      navigate("/login", { replace: true });
    } catch (error) {
      setLogoutError(getErrorMessage(error, "Unable to log out. Please try again."));
    }
  }

  return (
    <>
      {open && (
        <button
          type="button"
          aria-label="Close navigation"
          className="fixed inset-0 z-30 bg-black/65 backdrop-blur-sm md:hidden"
          onClick={onClose}
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-[264px] flex-col border-r border-slate-800/80 bg-[#0b1020] transition-transform duration-200 md:sticky md:top-0 md:h-screen md:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-[68px] items-center gap-3 border-b border-slate-800/80 px-5">
          <div className="grid h-8 w-8 place-items-center rounded-[10px] bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-sm shadow-indigo-950/40">
            <span className="text-[11px] font-bold tracking-[-0.04em]">AI</span>
          </div>
          <div className="min-w-0">
            <p className="truncate text-[13px] font-semibold tracking-tight text-slate-100">
              AI Proxy Router
            </p>
            <p className="mt-0.5 text-[10px] font-medium tracking-wide text-slate-500">
              DEVELOPER CONSOLE
            </p>
          </div>
        </div>

        <nav aria-label="Main navigation" className="flex-1 space-y-1 px-3 py-6">
          <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
            Workspace
          </p>
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              onClick={onClose}
              className={({ isActive }) =>
                `relative flex h-10 items-center gap-3 rounded-lg px-3 text-[13px] font-medium transition-colors ${
                  isActive
                    ? "bg-indigo-500/10 text-indigo-200 ring-1 ring-inset ring-indigo-400/20"
                    : "text-slate-400 hover:bg-slate-800/70 hover:text-slate-100"
                }`
              }
            >
              <Icon name={link.icon} size={17} />
              {link.label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-slate-800/80 p-3">
          {logoutError && (
            <p role="alert" className="mb-2 px-2 text-xs leading-5 text-rose-300">
              {logoutError}
            </p>
          )}
          <div className="flex items-center gap-3 rounded-xl px-2 py-2 transition-colors hover:bg-slate-800/60">
            <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-slate-800 text-xs font-semibold text-slate-200 ring-1 ring-inset ring-slate-700">
              {(user?.first_name?.[0] || user?.email?.[0] || "U").toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-[13px] font-medium text-slate-200">
                {fullName || "Workspace member"}
              </p>
              <p className="truncate text-xs text-slate-500">{user?.email}</p>
            </div>
            <button
              type="button"
              onClick={handleLogout}
              title="Log out"
              aria-label="Log out"
              className="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-slate-500 transition-colors hover:bg-slate-700 hover:text-slate-100"
            >
              <Icon name="logout" size={17} />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}

export default Sidebar;
