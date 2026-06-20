import { useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../../lib/api";
import { fmtMoney } from "../../lib/utils";

interface Props {
  symbol?: string; // if given, fetch single-symbol history; else portfolio aggregate
  period?: string;
  height?: number;
}

const PERIOD_OPTIONS = [
  { label: "1月", value: "1mo" },
  { label: "3月", value: "3mo" },
  { label: "6月", value: "6mo" },
  { label: "1年", value: "1y" },
  { label: "5年", value: "5y" },
];

export function HistoryLine({ symbol, period: initialPeriod = "1y", height = 280 }: Props) {
  const [period, setPeriod] = useState(initialPeriod);
  const [data, setData] = useState<{ date: string; value: number }[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const fetcher = symbol
      ? api.marketHistory(symbol, period)
      : api.history(period);
    fetcher
      .then((res) => {
        if (cancelled) return;
        const points = res.points || [];
        const closeKey = symbol ? "close" : "value";
        setData(
          points.map((p: any) => ({
            date: p.date,
            value: p[closeKey],
          }))
        );
      })
      .catch(() => {
        if (!cancelled) setData([]);
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [symbol, period]);

  const last = data.length ? data[data.length - 1].value : 0;
  const first = data.length ? data[0].value : 0;
  const change = last - first;
  const stroke = change >= 0 ? "#22c55e" : "#ef4444";

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <div className="text-xs text-muted">
          {symbol ? `${symbol} 净值` : "组合净值"}
          {data.length > 0 && (
            <span className="ml-2" style={{ color: stroke }}>
              {fmtMoney(change)} ({((change / first) * 100).toFixed(2)}%)
            </span>
          )}
        </div>
        <div className="flex gap-1">
          {PERIOD_OPTIONS.map((p) => (
            <button
              key={p.value}
              onClick={() => setPeriod(p.value)}
              className={`rounded px-2 py-1 text-xs transition-colors ${
                period === p.value
                  ? "bg-brand/20 text-brand-light"
                  : "text-muted hover:bg-bg-subtle hover:text-slate-100"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>
      <div style={{ height }} className="relative">
        {loading ? (
          <div className="flex h-full items-center justify-center text-sm text-muted">
            加载中…
          </div>
        ) : data.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-muted">
            暂无数据
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={stroke} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={stroke} stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="date"
                tick={{ fill: "#8a96ad", fontSize: 11 }}
                tickLine={false}
                axisLine={{ stroke: "#243049" }}
                minTickGap={40}
              />
              <YAxis
                tick={{ fill: "#8a96ad", fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                domain={["auto", "auto"]}
                width={50}
                tickFormatter={(v) => `$${(v / 1000).toFixed(1)}k`}
              />
              <Tooltip
                contentStyle={{
                  background: "#121826",
                  border: "1px solid #243049",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                labelStyle={{ color: "#8a96ad" }}
                formatter={(v: number) => [fmtMoney(v), "净值"]}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke={stroke}
                strokeWidth={2}
                fill="url(#grad)"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
