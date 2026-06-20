import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { TrendingUp, AlertCircle } from "lucide-react";
import { api, setToken } from "../lib/api";
import { Button, Field } from "../components/ui";

export default function Login() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const fn = mode === "login" ? api.login : api.register;
      const { access_token } = await fn(username.trim(), password);
      setToken(access_token);
      navigate("/dashboard", { replace: true });
    } catch (err: any) {
      setError(err.message || "操作失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg p-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center text-center">
          <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand/15 text-brand">
            <TrendingUp size={28} />
          </div>
          <h1 className="text-xl font-semibold">Stock Cockpit</h1>
          <p className="mt-1 text-sm text-muted">美股投资驾驶舱 · 登录进入</p>
        </div>

        <div className="rounded-2xl border border-border bg-bg-card p-6">
          <div className="mb-5 flex rounded-lg bg-bg p-1">
            {(["login", "register"] as const).map((m) => (
              <button
                key={m}
                onClick={() => {
                  setMode(m);
                  setError("");
                }}
                className={`flex-1 rounded-md py-2 text-sm font-medium transition-colors ${
                  mode === m
                    ? "bg-bg-subtle text-slate-100"
                    : "text-muted hover:text-slate-100"
                }`}
              >
                {m === "login" ? "登录" : "注册"}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="space-y-4">
            <Field
              label="用户名"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="admin"
              autoComplete="username"
              required
            />
            <Field
              label="密码"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              required
            />

            {error && (
              <div className="flex items-start gap-2 rounded-lg bg-neg/10 p-3 text-sm text-neg">
                <AlertCircle size={16} className="mt-0.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <Button type="submit" loading={loading} className="w-full" size="lg">
              {mode === "login" ? "登录" : "注册并登录"}
            </Button>
          </form>

          <p className="mt-5 text-center text-xs text-muted">
            首次启动时系统会自动创建 <code className="rounded bg-bg px-1 py-0.5">admin</code> 账户，<br />
            密码会打印在后台启动日志中。
          </p>
        </div>
      </div>
    </div>
  );
}
