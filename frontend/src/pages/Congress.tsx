import { useCallback, useEffect, useState } from "react";
import { Landmark, RefreshCw, TrendingUp, TrendingDown } from "lucide-react";
import { api } from "../lib/api";
import { Button, Card, CardHeader, CardTitle } from "../components/ui";
import { cn, fmtDate } from "../lib/utils";

interface Trade {
  id: number;
  symbol: string;
  politician: string;
  chamber: string;
  party: string;
  transaction_type: string;
  amount: string;
  traded_at: string | null;
  source: string;
}

export default function Congress() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filterType, setFilterType] = useState<string | null>(null);
  const [filterSym, setFilterSym] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.congress();
      setTrades(r.items || []);
    } catch {
      setTrades([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function refresh() {
    setRefreshing(true);
    try {
      await api.refreshCongress();
      await load();
    } finally {
      setRefreshing(false);
    }
  }

  const symbols = Array.from(new Set(trades.map((t) => t.symbol))).filter(Boolean);
  const shown = trades
    .filter((t) => !filterType || t.transaction_type === filterType)
    .filter((t) => !filterSym || t.symbol === filterSym);

  const buyCount = trades.filter((t) => t.transaction_type === "Buy").length;
  const sellCount = trades.filter((t) => t.transaction_type === "Sell").length;

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-semibold">
            <Landmark size={20} className="text-brand" /> 政客 / 内部人交易追踪
          </h1>
          <p className="text-sm text-muted">美国国会议员、内部人（CEO/高管）的股票交易动向</p>
        </div>
        <Button onClick={refresh} loading={refreshing} variant="secondary" size="sm">
          {!refreshing && <RefreshCw size={14} />} 刷新数据
        </Button>
      </div>

      {/* 统计 */}
      <div className="grid grid-cols-3 gap-3">
        <Card className="!p-3">
          <div className="text-xs text-muted">总交易</div>
          <div className="text-2xl font-semibold">{trades.length}</div>
        </Card>
        <Card className="!p-3">
          <div className="text-xs text-muted">买入</div>
          <div className="flex items-center gap-1 text-2xl font-semibold text-pos">
            <TrendingUp size={18} /> {buyCount}
          </div>
        </Card>
        <Card className="!p-3">
          <div className="text-xs text-muted">卖出</div>
          <div className="flex items-center gap-1 text-2xl font-semibold text-neg">
            <TrendingDown size={18} /> {sellCount}
          </div>
        </Card>
      </div>

      {trades.length === 0 ? (
        <Card className="flex flex-col items-center gap-4 py-12 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-brand/10 text-brand">
            <Landmark size={26} />
          </div>
          <div>
            <h3 className="font-medium text-slate-200">当前没有政客交易数据</h3>
            <p className="mx-auto mt-2 max-w-md text-sm text-muted">
              默认的公开数据源（Capitol Trades）目前无法抓取（有反爬保护）。
              <br /><br />
              <strong className="text-slate-300">要启用这个功能，需要配置 Quiver Quant 免费 token：</strong>
              <br />
              1. 访问 <a href="https://www.quiverquant.com" target="_blank" className="text-brand-light underline">quiverquant.com</a> 注册（免费）
              <br />
              2. 在 .env 文件添加：<code className="rounded bg-bg px-1.5 py-0.5 text-xs">QUIVER_API_TOKEN=你的token</code>
              <br />
              3. 重启：docker compose restart
            </p>
          </div>
          <Button onClick={refresh} loading={refreshing} variant="secondary" size="sm">
            <RefreshCw size={14} /> 重新尝试抓取
          </Button>
        </Card>
      ) : (
        <>
          {/* 过滤器 */}
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => setFilterType(null)}
              className={cn(
                "rounded-full px-3 py-1 text-xs transition-colors",
                !filterType ? "bg-brand text-white" : "bg-bg-card text-muted hover:text-slate-100"
              )}
            >
              全部
            </button>
            {["Buy", "Sell"].map((t) => (
              <button
                key={t}
                onClick={() => setFilterType(t)}
                className={cn(
                  "rounded-full px-3 py-1 text-xs transition-colors",
                  filterType === t
                    ? t === "Buy" ? "bg-pos text-white" : "bg-neg text-white"
                    : "bg-bg-card text-muted hover:text-slate-100"
                )}
              >
                {t === "Buy" ? "买入" : "卖出"}
              </button>
            ))}
            <span className="mx-2 text-muted">|</span>
            {symbols.slice(0, 12).map((s) => (
              <button
                key={s}
                onClick={() => setFilterSym(filterSym === s ? null : s)}
                className={cn(
                  "rounded-full px-3 py-1 text-xs transition-colors",
                  filterSym === s ? "bg-brand text-white" : "bg-bg-card text-muted hover:text-slate-100"
                )}
              >
                {s}
              </button>
            ))}
          </div>

          {/* 交易列表 */}
          <Card className="!p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-muted">
                    <th className="px-3 py-2.5 font-medium">标的</th>
                    <th className="px-3 py-2.5 font-medium">交易人</th>
                    <th className="px-3 py-2.5 font-medium">身份</th>
                    <th className="px-3 py-2.5 font-medium">方向</th>
                    <th className="px-3 py-2.5 font-medium">金额</th>
                    <th className="px-3 py-2.5 font-medium">交易日期</th>
                    <th className="px-3 py-2.5 font-medium">来源</th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((t) => (
                    <tr key={t.id} className="border-b border-border/50 last:border-0 hover:bg-bg-subtle/30">
                      <td className="px-3 py-2.5 font-medium">{t.symbol}</td>
                      <td className="px-3 py-2.5">{t.politician}</td>
                      <td className="px-3 py-2.5 text-xs text-muted">
                        {t.chamber} {t.party && <span className="ml-1">({t.party})</span>}
                      </td>
                      <td className="px-3 py-2.5">
                        <span
                          className={cn(
                            "rounded px-1.5 py-0.5 text-xs font-medium",
                            t.transaction_type === "Buy" ? "bg-pos/15 text-pos" : "bg-neg/15 text-neg"
                          )}
                        >
                          {t.transaction_type === "Buy" ? "买入" : "卖出"}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 text-xs text-muted">{t.amount || "—"}</td>
                      <td className="px-3 py-2.5 text-xs text-muted">{fmtDate(t.traded_at) || "—"}</td>
                      <td className="px-3 py-2.5 text-xs text-muted">{t.source}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}

      <p className="text-xs text-muted">
        💡 数据延迟说明：议员交易依法需在 30-45 天内披露，所以你看到的通常是 1-2 个月前的交易。
        这是"参考大资金方向"的长期线索，不适合用来当天跟风短线。
      </p>
    </div>
  );
}
