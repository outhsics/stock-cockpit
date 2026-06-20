import { useCallback, useEffect, useState } from "react";
import { Microscope, Activity, Scale, TrendingUp, Search, BarChart3 } from "lucide-react";
import { api } from "../lib/api";
import { Button, Card, CardHeader, CardTitle, Input } from "../components/ui";
import { cn, fmtMoney, colorForChange, fmtPct } from "../lib/utils";

type MacroItem = { label: string; symbol: string; price: number | null; day_change_pct: number | null };
type Fundamentals = Record<string, any>;
type PerfItem = Record<string, any>;

export default function Research() {
  const [macro, setMacro] = useState<MacroItem[]>([]);
  const [macroLoading, setMacroLoading] = useState(true);
  const [symbol, setSymbol] = useState("QQQ");
  const [fund, setFund] = useState<Fundamentals | null>(null);
  const [perf, setPerf] = useState<PerfItem | null>(null);
  const [compareInput, setCompareInput] = useState("QQQ,VOO,SPY");
  const [compareData, setCompareData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const loadMacro = useCallback(async () => {
    setMacroLoading(true);
    try {
      // Race with a 60s timeout — if the data source is slow/limited, show
      // the degraded UI instead of spinning forever.
      const r = await Promise.race([
        api.macro(),
        new Promise<any>((_, reject) => setTimeout(() => reject(new Error("timeout")), 60000)),
      ]);
      setMacro(r.indicators || []);
    } catch {
      setMacro([]);
    } finally {
      setMacroLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMacro();
  }, [loadMacro]);

  const [err, setErr] = useState("");
  const lookup = async (sym?: string) => {
    const s = (sym ?? symbol).trim().toUpperCase();
    if (!s) return;
    setLoading(true);
    setErr("");
    try {
      const timeoutP = new Promise<never>((_, rej) =>
        setTimeout(() => rej(new Error("查询超时（数据源限流），请稍后重试")), 45000)
      );
      const [f, p] = await Promise.race([
        Promise.all([
          api.fundamentals(s),
          api.performance(s).catch(() => ({ returns: {} })),
        ]),
        timeoutP,
      ]);
      setFund(f);
      setPerf(p);
    } catch (e: any) {
      setFund(null);
      setPerf(null);
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  const compare = async () => {
    const syms = compareInput.split(",").map((s) => s.trim()).filter(Boolean);
    if (!syms.length) return;
    setLoading(true);
    setErr("");
    try {
      const r = await Promise.race([
        api.compare(syms),
        new Promise<any>((_, rej) => setTimeout(() => rej(new Error("对比查询超时，请稍后重试")), 60000)),
      ]);
      setCompareData(r.items || []);
    } catch (e: any) {
      setCompareData([]);
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-semibold">
            <Microscope size={20} className="text-brand" /> 深度研究
          </h1>
          <p className="text-sm text-muted">宏观温度计 · ETF 对比 · 个股基本面 · 区间表现</p>
        </div>
      </div>

      {/* 宏观温度计 */}
      <Card>
        <CardHeader>
          <CardTitle>
            <span className="flex items-center gap-2 text-slate-200">
              <Activity size={15} /> 宏观温度计
            </span>
          </CardTitle>
          <button onClick={loadMacro} className="text-xs text-muted hover:text-slate-100">刷新</button>
        </CardHeader>
        {macroLoading ? (
          <div className="py-6 text-center text-sm text-muted">
            <div>正在获取各大类资产行情…</div>
            <div className="mt-1 text-xs">（数据源免费版有节流，约需 30-60 秒；可稍后点「刷新」）</div>
          </div>
        ) : macro.length === 0 ? (
          <div className="py-6 text-center text-sm text-muted">
            <div>行情暂时不可用（免费数据源限流中）</div>
            <button onClick={loadMacro} className="mt-2 text-xs text-brand-light hover:underline">点此重试</button>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
            {macro.map((m) => (
              <div key={m.symbol} className="rounded-lg border border-border bg-bg p-3">
                <div className="text-xs text-muted">{m.label}</div>
                <div className="mt-1 font-mono text-lg font-semibold">
                  {m.price ? fmtMoney(m.price) : "—"}
                </div>
                <div className={cn("text-xs font-medium", colorForChange(m.day_change_pct ?? 0))}>
                  {m.day_change_pct !== null ? fmtPct(m.day_change_pct) : "—"}
                </div>
              </div>
            ))}
          </div>
        )}
        <p className="mt-3 text-xs text-muted">通过代表性 ETF 观察各大类资产当日表现（SPY/QQQ=美股、TLT=美债、GLD=黄金、UVXY=波动率）</p>
      </Card>

      {/* 个股基本面 */}
      <Card>
        <CardHeader>
          <CardTitle>
            <span className="flex items-center gap-2 text-slate-200">
              <Scale size={15} /> 个股/ETF 基本面
            </span>
          </CardTitle>
        </CardHeader>
        <div className="mb-4 flex gap-2">
          <Input
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && lookup()}
            placeholder="输入代码，如 QQQ / AAPL / VOO"
            className="max-w-xs"
          />
          <Button onClick={() => lookup()} loading={loading} variant="secondary" size="md">
            <Search size={14} /> 查询
          </Button>
        </div>
        {loading && (
          <div className="mb-2 rounded-lg bg-bg-subtle px-3 py-2 text-xs text-brand-light">
            正在查询 {symbol}（数据源免费版有节流，约需 10-40 秒）…
          </div>
        )}
        {err && (
          <div className="mb-2 rounded-lg bg-neg/10 px-3 py-2 text-sm text-neg">
            ⚠️ {err}
          </div>
        )}
        {fund && (
          <div className="space-y-4">
            <div>
              <div className="text-base font-semibold">
                {fund.name} <span className="text-muted">· {fund.symbol}</span>
              </div>
              <div className="text-xs text-muted">
                {[fund.type, fund.sector, fund.industry].filter(Boolean).join(" · ")}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <Metric label="市盈率 P/E" value={fund.pe_ratio} fmt={(v) => Number(v).toFixed(2)} />
              <Metric label="前瞻 P/E" value={fund.forward_pe} fmt={(v) => Number(v).toFixed(2)} />
              <Metric label="PEG" value={fund.peg_ratio} fmt={(v) => Number(v).toFixed(2)} />
              <Metric label="市净率 P/B" value={fund.pb_ratio} fmt={(v) => Number(v).toFixed(2)} />
              <Metric label="市值" value={fund.market_cap} fmt={(v) => fmtCompact(v)} />
              <Metric label="股息率" value={fund.dividend_yield} fmt={(v) => `${(v * 100).toFixed(2)}%`} />
              <Metric label="Beta" value={fund.beta} fmt={(v) => Number(v).toFixed(2)} />
              <Metric label="费率(ETF)" value={fund.expense_ratio} fmt={(v) => `${(v * 100).toFixed(3)}%`} />
              <Metric label="52周高" value={fund["52w_high"]} fmt={(v) => fmtMoney(v)} />
              <Metric label="52周低" value={fund["52w_low"]} fmt={(v) => fmtMoney(v)} />
              <Metric label="EPS" value={fund.eps} fmt={(v) => fmtMoney(v)} />
            </div>

            {/* 区间表现 */}
            {perf?.returns && Object.keys(perf.returns).length > 0 && (
              <div>
                <div className="mb-2 flex items-center gap-2 text-sm text-slate-200">
                  <TrendingUp size={14} /> 区间收益率
                </div>
                <div className="grid grid-cols-4 gap-3">
                  {Object.entries(perf.returns).map(([p, r]) => (
                    <div key={p} className="rounded-lg border border-border bg-bg p-3 text-center">
                      <div className="text-xs text-muted">{p}</div>
                      <div className={cn("mt-1 font-mono text-lg font-semibold", colorForChange((r as number) ?? 0))}>
                        {r !== null ? fmtPct(r as number) : "—"}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {fund.description && (
              <div className="border-t border-border pt-3">
                <div className="mb-1 text-xs text-muted">公司/基金简介</div>
                <p className="text-sm leading-relaxed text-slate-300">{fund.description.slice(0, 600)}</p>
              </div>
            )}
          </div>
        )}
      </Card>

      {/* ETF 对比 */}
      <Card>
        <CardHeader>
          <CardTitle>
            <span className="flex items-center gap-2 text-slate-200">
              <BarChart3 size={15} /> ETF / 股票对比
            </span>
          </CardTitle>
        </CardHeader>
        <div className="mb-4 flex gap-2">
          <Input
            value={compareInput}
            onChange={(e) => setCompareInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && compare()}
            placeholder="多个代码用逗号分隔，如 QQQ,VOO,SPY"
            className="max-w-md"
          />
          <Button onClick={compare} loading={loading} variant="secondary">
            <BarChart3 size={14} /> 对比
          </Button>
        </div>
        {compareData.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted">
                  <th className="px-2 py-2 font-medium">标的</th>
                  <th className="px-2 py-2 text-right font-medium">市值</th>
                  <th className="px-2 py-2 text-right font-medium">P/E</th>
                  <th className="px-2 py-2 text-right font-medium">股息率</th>
                  <th className="px-2 py-2 text-right font-medium">费率</th>
                  <th className="px-2 py-2 text-right font-medium">Beta</th>
                  <th className="px-2 py-2 text-right font-medium">52周高</th>
                  <th className="px-2 py-2 text-right font-medium">52周低</th>
                </tr>
              </thead>
              <tbody>
                {compareData.map((c) => (
                  <tr key={c.symbol} className="border-b border-border/50 last:border-0">
                    <td className="px-2 py-2.5">
                      <div className="font-medium">{c.symbol}</div>
                      <div className="text-xs text-muted">{(c.name || "").slice(0, 24)}</div>
                    </td>
                    <td className="px-2 py-2.5 text-right font-mono">{c.market_cap ? fmtCompact(c.market_cap) : "—"}</td>
                    <td className="px-2 py-2.5 text-right font-mono">{c.pe_ratio ? Number(c.pe_ratio).toFixed(1) : "—"}</td>
                    <td className="px-2 py-2.5 text-right font-mono">{c.dividend_yield ? `${(c.dividend_yield * 100).toFixed(2)}%` : "—"}</td>
                    <td className="px-2 py-2.5 text-right font-mono">{c.expense_ratio ? `${(c.expense_ratio * 100).toFixed(3)}%` : "—"}</td>
                    <td className="px-2 py-2.5 text-right font-mono">{c.beta ? Number(c.beta).toFixed(2) : "—"}</td>
                    <td className="px-2 py-2.5 text-right font-mono">{c["52w_high"] ? fmtMoney(c["52w_high"]) : "—"}</td>
                    <td className="px-2 py-2.5 text-right font-mono">{c["52w_low"] ? fmtMoney(c["52w_low"]) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function Metric({ label, value, fmt }: { label: string; value: any; fmt: (v: any) => string }) {
  const hasVal = value !== null && value !== undefined && value !== "";
  return (
    <div className="rounded-lg border border-border bg-bg p-3">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 font-mono text-sm font-medium">
        {hasVal ? fmt(value) : <span className="text-muted">—</span>}
      </div>
    </div>
  );
}

function fmtCompact(v: any): string {
  const n = Number(v);
  if (!n) return "—";
  if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  return fmtMoney(n);
}
