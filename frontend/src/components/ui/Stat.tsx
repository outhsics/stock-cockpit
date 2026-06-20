import { Card } from "./Card";
import { cn, colorForChange } from "../../lib/utils";

interface StatCardProps {
  label: string;
  value: string;
  delta?: string;
  deltaValue?: number;
  hint?: string;
  icon?: React.ReactNode;
}

export function StatCard({ label, value, delta, deltaValue, hint, icon }: StatCardProps) {
  return (
    <Card className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted">{label}</span>
        {icon && <span className="text-muted">{icon}</span>}
      </div>
      <div className="text-2xl font-semibold tracking-tight">{value}</div>
      {delta !== undefined && (
        <div className={cn("text-xs font-medium", colorForChange(deltaValue ?? 0))}>{delta}</div>
      )}
      {hint && <div className="text-[11px] text-muted">{hint}</div>}
    </Card>
  );
}
