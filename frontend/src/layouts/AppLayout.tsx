import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  Wallet,
  Sparkles,
  Newspaper,
  MessageSquare,
  Microscope,
  Landmark,
  LogOut,
  TrendingUp,
  Menu,
  X,
} from "lucide-react";
import { api, isLoggedIn, setToken } from "../lib/api";
import { cn } from "../lib/utils";

const NAV = [
  { to: "/dashboard", label: "总览", icon: LayoutDashboard },
  { to: "/portfolio", label: "持仓", icon: Wallet },
  { to: "/briefing", label: "AI 简报", icon: Sparkles },
  { to: "/chat", label: "AI 问答", icon: MessageSquare },
  { to: "/research", label: "深度研究", icon: Microscope },
  { to: "/news", label: "新闻", icon: Newspaper },
  { to: "/congress", label: "政客追踪", icon: Landmark },
];

export default function AppLayout() {
  const navigate = useNavigate();
  const [username, setUsername] = useState<string>("");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    if (!isLoggedIn()) {
      navigate("/login", { replace: true });
      return;
    }
    api.me().then((u) => setUsername(u.username)).catch(() => {});
  }, [navigate]);

  function logout() {
    setToken(null);
    navigate("/login", { replace: true });
  }

  return (
    <div className="flex h-screen bg-bg text-slate-100">
      {/* Sidebar */}
      <aside
        className={cn(
          "fixed md:static z-40 h-full w-64 shrink-0 border-r border-border bg-bg-card transition-transform",
          sidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        )}
      >
        <div className="flex h-16 items-center gap-2 border-b border-border px-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand/15 text-brand">
            <TrendingUp size={20} />
          </div>
          <div>
            <div className="font-semibold leading-tight">Stock Cockpit</div>
            <div className="text-[11px] text-muted">美股投资驾驶舱</div>
          </div>
          <button
            className="ml-auto md:hidden text-muted hover:text-slate-100"
            onClick={() => setSidebarOpen(false)}
          >
            <X size={18} />
          </button>
        </div>

        <nav className="space-y-1 p-3">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors",
                  isActive
                    ? "bg-brand/15 text-brand-light font-medium"
                    : "text-muted hover:bg-bg-subtle hover:text-slate-100"
                )
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="absolute bottom-0 left-0 right-0 border-t border-border p-3">
          <div className="mb-2 flex items-center gap-2 px-3 py-2 text-xs text-muted">
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-bg-subtle text-slate-200">
              {username.slice(0, 1).toUpperCase() || "?"}
            </div>
            <span className="truncate">{username || "loading…"}</span>
          </div>
          <button
            onClick={logout}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-muted transition-colors hover:bg-neg/10 hover:text-neg"
          >
            <LogOut size={18} />
            退出登录
          </button>
        </div>
      </aside>

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 items-center gap-3 border-b border-border bg-bg-card/60 px-4 backdrop-blur md:hidden">
          <button
            onClick={() => setSidebarOpen(true)}
            className="text-muted hover:text-slate-100"
          >
            <Menu size={20} />
          </button>
          <span className="font-medium">Stock Cockpit</span>
        </header>

        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
