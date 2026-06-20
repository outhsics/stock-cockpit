import { useCallback, useEffect, useState } from "react";
import { Plus, Trash2, X, Info, RefreshCw } from "lucide-react";
import { api } from "../lib/api";
import { Button, Card, CardHeader, CardTitle, Field, Input } from "../components/ui";
import { HistoryLine } from "../components/charts/HistoryLine";
import { cn, colorForChange, fmtMoney, fmtPct } from "../lib/utils";

export default function Portfolio() {
  const [holdings, setHoldings] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [info, setInfo] = useState<any>(null);

  const load = useCallback(async () => {
    try {
      setHoldings(await api.holdings());
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshPrices = useCallback(async () => {
    setRefreshing(true);
    api.refreshPrices().catch(() => {});  // fire-and-forget
    setTimeout(async () => {
      await load();
      setRefreshing(false);
    }, 15000);
  }, [load]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!selected) {
      setInfo(null);
      return;
    }
    api.info(selected).then(setInfo).catch(() => setInfo(null));
  }, [selected]);

  const selectedHolding = holdings.find((h) => h.symbol === selected);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold">持仓管理</h1>
          <p className="text-sm text-muted">添加你持有的美股 / ETF</p>
        </div>
        <div className="flex gap-2">
          <Button onClick={refreshPrices} loading={refreshing} variant="secondary" size="sm">
            {!refreshing && <RefreshCw size={14} />} 刷新行情
          </Button>
          <Button onClick={() => setShowAdd(true)} size="sm">
            <Plus size={14} /> 添加持仓
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="flex h-40 items-center justify-center text-muted">加载中…</div>
      ) : holdings.length === 0 ? (
        <Card className="flex flex-col items-center gap-3 py-12 text-center">
          <div className="text-muted">还没有持仓</div>
          <Button onClick={() => setShowAdd(true)} size="sm">
            添加你的第一个持仓
          </Button>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>我的持仓（{holdings.length}）</CardTitle>
          </CardHeader>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted">
                  <th className="px-2 py-2 font-medium">标的</th>
                  <th className="px-2 py-2 text-right font-medium">股数</th>
                  <th className="px-2 py-2 text-right font-medium">成本</th>
                  <th className="px-2 py-2 text-right font-medium">现价</th>
                  <th className="px-2 py-2 text-right font-medium">今日</th>
                  <th className="px-2 py-2 text-right font-medium">市值</th>
                  <th className="px-2 py-2 text-right font-medium">盈亏</th>
                  <th className="px-2 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {holdings.map((h) => (
                  <tr
                    key={h.id}
                    className="cursor-pointer border-b border-border/50 last:border-0 hover:bg-bg-subtle/40"
                    onClick={() => setSelected(h.symbol)}
                  >
                    <td className="px-2 py-2.5">
                      <div className="font-medium">{h.symbol}</div>
                      <div className="text-xs text-muted">{h.name}</div>
                    </td>
                    <td className="px-2 py-2.5 text-right">{h.shares}</td>
                    <td className="px-2 py-2.5 text-right">{fmtMoney(h.cost_basis)}</td>
                    <td className="px-2 py-2.5 text-right">{fmtMoney(h.current_price)}</td>
                    <td className={cn("px-2 py-2.5 text-right", colorForChange(h.day_change_pct))}>
                      {fmtPct(h.day_change_pct)}
                    </td>
                    <td className="px-2 py-2.5 text-right">{fmtMoney(h.market_value)}</td>
                    <td className={cn("px-2 py-2.5 text-right", colorForChange(h.pnl))}>
                      <div>{fmtMoney(h.pnl)}</div>
                      <div className="text-xs">{fmtPct(h.pnl_pct)}</div>
                    </td>
                    <td className="px-2 py-2.5 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          if (confirm(`删除持仓 ${h.symbol}？`)) {
                            api.deleteHolding(h.id).then(load);
                          }
                        }}
                        className="text-muted hover:text-neg"
                      >
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Detail drawer */}
      {selected && (
        <Card>
          <CardHeader>
            <CardTitle>
              {selected} · 详情
              {selectedHolding && (
                <span className="ml-2 text-xs text-muted">
                  持仓 {selectedHolding.shares} 股 · 市值 {fmtMoney(selectedHolding.market_value)}
                </span>
              )}
            </CardTitle>
            <button onClick={() => setSelected(null)} className="text-muted hover:text-slate-100">
              <X size={16} />
            </button>
          </CardHeader>
          <HistoryLine symbol={selected} period="1y" height={260} />
          {info && (
            <div className="mt-4 grid grid-cols-2 gap-3 border-t border-border pt-4 text-sm md:grid-cols-4">
              <Info2 label="类型" value={info.type} />
              <Info2 label="交易所" value={info.exchange} />
              <Info2
                label="费率"
                value={info.expense_ratio ? `${(info.expense_ratio * 100).toFixed(2)}%` : "—"}
              />
              <Info2
                label="股息率"
                value={info.yield != null ? `${(info.yield * 100).toFixed(2)}%` : "—"}
              />
              {info.description && (
                <div className="col-span-full mt-2 text-xs leading-relaxed text-muted">
                  {info.description.slice(0, 400)}
                  {info.description.length > 400 ? "…" : ""}
                </div>
              )}
            </div>
          )}
        </Card>
      )}

      {showAdd && <AddHoldingModal onClose={() => setShowAdd(false)} onAdded={load} />}
    </div>
  );
}

function Info2({ label, value }: { label: string; value: any }) {
  return (
    <div>
      <div className="text-xs text-muted">{label}</div>
      <div className="font-medium">{value || "—"}</div>
    </div>
  );
}

function AddHoldingModal({
  onClose,
  onAdded,
}: {
  onClose: () => void;
  onAdded: () => void;
}) {
  const [symbol, setSymbol] = useState("");
  const [shares, setShares] = useState("");
  const [cost, setCost] = useState("");
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState<any>(null);

  // Preview is best-effort and non-blocking: it only shows if the price is
  // already cached server-side. We never block the form on a slow quote fetch.
  const [previewing, setPreviewing] = useState(false);
  useEffect(() => {
    const sym = symbol.trim().toUpperCase();
    if (!sym) {
      setPreview(null);
      return;
    }
    setPreviewing(true);
    const t = setTimeout(() => {
      // Race with a short timeout — if quote is slow, just skip the preview.
      Promise.race([
        api.quote(sym).then(setPreview).catch(() => setPreview(null)),
        new Promise((r) => setTimeout(r, 3000)), // max 3s for preview
      ]).finally(() => setPreviewing(false));
    }, 500);
    return () => clearTimeout(t);
  }, [symbol]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.addHolding({
        symbol: symbol.trim().toUpperCase(),
        shares: parseFloat(shares),
        cost_basis: parseFloat(cost),
        note: note.trim(),
      });
      onAdded();
      onClose();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-2xl border border-border bg-bg-card p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 className="font-semibold">添加持仓</h3>
          <button onClick={onClose} className="text-muted hover:text-slate-100">
            <X size={18} />
          </button>
        </div>
        <form onSubmit={submit} className="space-y-3">
          <Field
            label="股票/ETF 代码"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            placeholder="QQQ / VOO / AAPL"
            required
          />
          {preview && !preview.error && (
            <div className="rounded-lg bg-brand/10 px-3 py-2 text-xs text-brand-light">
              <Info size={12} className="mr-1 inline" />
              {preview.name} · 现价 {fmtMoney(preview.price)} · 今日 {fmtPct(preview.day_change_pct)}
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <Field
              label="股数"
              type="number"
              step="any"
              value={shares}
              onChange={(e) => setShares(e.target.value)}
              placeholder="10"
              required
            />
            <Field
              label="平均成本 ($)"
              type="number"
              step="any"
              value={cost}
              onChange={(e) => setCost(e.target.value)}
              placeholder="350.00"
              required
            />
          </div>
          <Field
            label="备注（可选）"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="长期定投 / 短线观察…"
          />
          {error && <div className="rounded-lg bg-neg/10 p-2 text-sm text-neg">{error}</div>}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="ghost" onClick={onClose}>
              取消
            </Button>
            <Button type="submit" loading={loading}>
              添加
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
