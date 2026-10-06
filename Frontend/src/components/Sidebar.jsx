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
          className="fixed inset-0 z-30 bg-slate-950/30 md:hidden"
          onClick={onClose}
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-[264px] flex-col border-r border-slate-200 bg-white transition-transform duration-200 md:static md:z-auto md:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-[68px] items-center gap-3 border-b border-slate-100 px-5">
          <div className="grid h-8 w-8 place-items-center rounded-lg bg-indigo-600 text-white shadow-sm">
            <span className="text-sm font-semibold tracking-tight">AI</span>
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-slate-950">
              AI Proxy Router
            </p>
            <p className="mt-0.5 text-[11px] text-slate-400">Developer console</p>
          </div>
        </div>

        <nav aria-label="Main navigation" className="flex-1 space-y-1 px-3 py-5">
          <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.13em] text-slate-400">
            Workspace
          </p>
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              onClick={onClose}
              className={({ isActive }) =>
                `flex h-10 items-center gap-3 rounded-lg px-3 text-[13px] font-medium transition-colors ${
                  isActive
                    ? "bg-indigo-50 text-indigo-700"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-950"
                }`
              }
            >
              <Icon name={link.icon} size={17} />
              {link.label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-slate-100 p-3">
          {logoutError && (
            <p role="alert" className="mb-2 px-2 text-xs leading-5 text-rose-700">
              {logoutError}
            </p>
          )}
          <div className="flex items-center gap-3 rounded-lg px-2 py-2">
            <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-slate-100 text-xs font-semibold text-slate-600">
              {(user?.first_name?.[0] || user?.email?.[0] || "U").toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-[13px] font-medium text-slate-800">
                {fullName || "Workspace member"}
              </p>
              <p className="truncate text-xs text-slate-400">{user?.email}</p>
            </div>
            <button
              type="button"
              onClick={handleLogout}
              title="Log out"
              aria-label="Log out"
              className="grid h-8 w-8 shrink-0 place-items-center rounded-md text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
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
