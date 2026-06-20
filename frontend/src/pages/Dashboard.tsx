import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Wallet, TrendingUp, TrendingDown, Sparkles, ArrowUpRight } from "lucide-react";
import { api } from "../lib/api";
import { Card, CardHeader, CardTitle, StatCard } from "../components/ui";
import { AllocationPie } from "../components/charts/AllocationPie";
import { HistoryLine } from "../components/charts/HistoryLine";
import { cn, colorForChange, fmtMoney, fmtPct } from "../lib/utils";

interface Overview {
  total_market_value: number;
  total_cost_value: number;
  total_pnl: number;
  total_pnl_pct: number;
  day_pnl: number;
  day_pnl_pct: number;
  holdings_count: number;
  top_movers: { symbol: string; day_change_pct: number }[];
  allocation: { symbol: string; value: number; pct: number }[];
}

export default function Dashboard() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [holdings, setHoldings] = useState<any[]>([]);
  const [latest, setLatest] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    // overview/holdings now use cached prices → instant. No network wait.
    try {
      const [ov, h, b] = await Promise.all([
        api.overview(),
        api.holdings(),
        api.latestBriefing().catch(() => null),
      ]);
      setOverview(ov);
      setHoldings(h);
      setLatest(b);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Trigger background price refresh (non-blocking) — fills cache so the
  // next load shows fresh prices. We DON'T await the network here; instead
  // we poll for updated cache after a delay so the UI stays responsive.
  const refreshPrices = useCallback(async () => {
    setRefreshing(true);
    // Fire the refresh without waiting on it (data sources can be slow).
    api.refreshPrices().catch(() => {});
    // Poll overview after the expected fetch window to pick up new cache.
    setTimeout(async () => {
      await load();
      setRefreshing(false);
    }, 15000);
  }, [load]);

  useEffect(() => {
    load();
    // Auto-refresh prices in the background after the page loads with cached
    // data, so prices become fresh within ~30s without blocking the UI.
    const t = setTimeout(() => refreshPrices(), 1500);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading && !overview) {
    return <div className="flex h-full items-center justify-center text-muted">加载中…</div>;
  }

  const ov = overview;
  const hasHoldings = (ov?.holdings_count ?? 0) > 0;

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold">投资总览</h1>
          <p className="text-sm text-muted">实时持仓表现 · {refreshing ? "正在后台刷新行情…" : "价格可能略有延迟，点击刷新获取最新"}</p>
        </div>
        <button
          onClick={refreshPrices}
          disabled={refreshing}
          className="rounded-lg px-3 py-1.5 text-xs text-muted hover:bg-bg-subtle hover:text-slate-100 disabled:opacity-50"
        >
          {refreshing ? "刷新中…" : "刷新行情"}
        </button>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="总市值"
          value={fmtMoney(ov?.total_market_value ?? 0)}
          icon={<Wallet size={16} />}
          hint={`${ov?.holdings_count ?? 0} 个持仓`}
        />
        <StatCard
          label="今日盈亏"
          value={fmtMoney(ov?.day_pnl ?? 0)}
          delta={fmtPct(ov?.day_pnl_pct ?? 0)}
          deltaValue={ov?.day_pnl_pct ?? 0}
          icon={(ov?.day_pnl ?? 0) >= 0 ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
        />
        <StatCard
          label="累计盈亏"
          value={fmtMoney(ov?.total_pnl ?? 0)}
          delta={fmtPct(ov?.total_pnl_pct ?? 0)}
          deltaValue={ov?.total_pnl_pct ?? 0}
        />
        <StatCard
          label="总成本"
          value={fmtMoney(ov?.total_cost_value ?? 0)}
          hint="投入资金"
        />
      </div>

      {!hasHoldings ? (
        <Card className="flex flex-col items-center gap-3 py-12 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand/10 text-brand">
            <Wallet size={22} />
          </div>
          <div>
            <h3 className="font-medium">还没有持仓</h3>
            <p className="mt-1 text-sm text-muted">
              去持仓页添加你的第一只 ETF（如 QQQ、VOO），即可看到全部数据。
            </p>
          </div>
          <Link
            to="/portfolio"
            className="mt-2 inline-flex items-center gap-1 rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-dark"
          >
            添加持仓 <ArrowUpRight size={14} />
          </Link>
        </Card>
      ) : (
        <>
          {/* Charts */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>净值曲线</CardTitle>
              </CardHeader>
              <HistoryLine period="1y" height={280} />
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>资产配置</CardTitle>
              </CardHeader>
              <AllocationPie data={ov?.allocation ?? []} />
            </Card>
          </div>

          {/* Holdings table */}
          <Card>
            <CardHeader>
              <CardTitle>持仓明细</CardTitle>
              <Link to="/portfolio" className="text-xs text-brand-light hover:underline">
                管理持仓 →
              </Link>
            </CardHeader>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-muted">
                    <th className="px-2 py-2 font-medium">标的</th>
                    <th className="px-2 py-2 text-right font-medium">现价</th>
                    <th className="px-2 py-2 text-right font-medium">今日</th>
                    <th className="px-2 py-2 text-right font-medium">市值</th>
                    <th className="px-2 py-2 text-right font-medium">盈亏</th>
                  </tr>
                </thead>
                <tbody>
                  {holdings.map((h) => (
                    <tr key={h.id} className="border-b border-border/50 last:border-0">
                      <td className="px-2 py-2.5">
                        <div className="font-medium">{h.symbol}</div>
                        <div className="text-xs text-muted">{h.name}</div>
                      </td>
                      <td className="px-2 py-2.5 text-right">{fmtMoney(h.current_price)}</td>
                      <td className={cn("px-2 py-2.5 text-right", colorForChange(h.day_change_pct))}>
                        {fmtPct(h.day_change_pct)}
                      </td>
                      <td className="px-2 py-2.5 text-right">{fmtMoney(h.market_value)}</td>
                      <td className={cn("px-2 py-2.5 text-right", colorForChange(h.pnl))}>
                        <div>{fmtMoney(h.pnl)}</div>
                        <div className="text-xs">{fmtPct(h.pnl_pct)}</div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Latest briefing preview */}
          {latest && (
            <Card>
              <CardHeader>
                <CardTitle>
                  <span className="flex items-center gap-2">
                    <Sparkles size={14} className="text-brand" /> 最新 AI 简报
                  </span>
                </CardTitle>
                <Link to="/briefing" className="text-xs text-brand-light hover:underline">
                  查看全部 →
                </Link>
              </CardHeader>
              <div className="prose-briefing max-h-40 overflow-hidden text-sm">
                <div
                  className="prose-briefing"
                  dangerouslySetInnerHTML={{
                    __html: (latest.content || "")
                      .replace(/^>\s+(.+)$/gm, "<blockquote>$1</blockquote>")
                      .slice(0, 600) + "…",
                  }}
                />
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
