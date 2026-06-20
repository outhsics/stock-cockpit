import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";

const COLORS = ["#3b82f6", "#22c55e", "#a855f7", "#f59e0b", "#ec4899", "#06b6d4", "#84cc16"];

interface Props {
  data: { symbol: string; value: number; pct: number }[];
}

export function AllocationPie({ data }: Props) {
  if (!data.length) {
    return (
      <div className="flex h-[260px] items-center justify-center text-sm text-muted">
        暂无持仓数据
      </div>
    );
  }
  return (
    <div className="h-[260px]">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="symbol"
            cx="50%"
            cy="50%"
            innerRadius={55}
            outerRadius={90}
            paddingAngle={2}
            stroke="none"
          >
            {data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              background: "#121826",
              border: "1px solid #243049",
              borderRadius: 8,
              fontSize: 12,
            }}
            formatter={(v: number, _n, p: any) => [
              `$${v.toLocaleString()} (${p.payload.pct}%)`,
              p.payload.symbol,
            ]}
          />
          <Legend
            verticalAlign="bottom"
            iconType="circle"
            wrapperStyle={{ fontSize: 12, color: "#8a96ad" }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
