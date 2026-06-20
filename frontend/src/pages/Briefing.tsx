import { useCallback, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Sparkles, RefreshCw, Clock, ChevronRight } from "lucide-react";
import { api } from "../lib/api";
import { Button, Card, CardHeader, CardTitle } from "../components/ui";
import { fmtDate } from "../lib/utils";

export default function Briefing() {
  const [current, setCurrent] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [b, list] = await Promise.all([
        api.latestBriefing(),
        api.listBriefings(20),
      ]);
      setCurrent(b);
      setHistory(list || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const [genProgress, setGenProgress] = useState("");
  async function generate() {
    setGenerating(true);
    setError("");
    setGenProgress("正在调用 AI 分析你的持仓和新闻，约需 20-40 秒，请稍候…");
    // 进度提示轮播
    const tips = [
      "正在调用 AI 分析你的持仓和新闻，约需 20-40 秒，请稍候…",
      "AI 正在解读最新财经新闻…",
      "AI 正在分析你的持仓异动…",
      "AI 正在生成操作建议…马上就好…",
    ];
    let ti = 0;
    const tipTimer = setInterval(() => {
      ti = (ti + 1) % tips.length;
      setGenProgress(tips[ti]);
    }, 8000);

    try {
      const b = await Promise.race([
        api.generateBriefing(),
        new Promise<never>((_, rej) =>
          setTimeout(() => rej(new Error("生成超时（90秒），请稍后重试。可能是 AI 服务繁忙。")), 90000)
        ),
      ]);
      setCurrent(b);
      await load();
    } catch (err: any) {
      setError(err.message);
    } finally {
      clearInterval(tipTimer);
      setGenerating(false);
      setGenProgress("");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-semibold">
            <Sparkles size={20} className="text-brand" /> AI 每日简报
          </h1>
          <p className="text-sm text-muted">基于你的持仓和最新新闻，由 AI 生成分析</p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Button onClick={generate} loading={generating} variant="secondary" size="sm" disabled={generating}>
            {!generating && <RefreshCw size={14} />}
            {generating ? "生成中…" : "立即生成"}
          </Button>
          {genProgress && (
            <span className="max-w-xs text-right text-[11px] text-brand-light">{genProgress}</span>
          )}
        </div>
      </div>

      {error && (
        <Card className="border-neg/30 bg-neg/5">
          <div className="text-sm text-neg">{error}</div>
        </Card>
      )}

      {loading ? (
        <div className="flex h-40 items-center justify-center text-muted">加载中…</div>
      ) : current ? (
        <Card>
          <CardHeader>
            <CardTitle>
              <span className="flex items-center gap-1.5 text-slate-200">
                <Clock size={13} />
                {fmtDate(current.created_at)}
                <span className="ml-2 rounded bg-bg-subtle px-1.5 py-0.5 text-[10px] text-muted">
                  {current.model}
                </span>
              </span>
            </CardTitle>
          </CardHeader>
          <div className="prose-briefing max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{current.content || ""}</ReactMarkdown>
          </div>
          <div className="mt-6 border-t border-border pt-3 text-[11px] text-muted">
            ⚠️ 本简报由 AI 自动生成，仅供参考，不构成投资建议。决策请自行判断并自担风险。
          </div>
        </Card>
      ) : (
        <Card className="flex flex-col items-center gap-3 py-12 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand/10 text-brand">
            <Sparkles size={22} />
          </div>
          <div>
            <h3 className="font-medium">还没有 AI 简报</h3>
            <p className="mt-1 text-sm text-muted">
              点击右上角"立即生成"，AI 会根据你的持仓和最新新闻写一份分析。
            </p>
          </div>
        </Card>
      )}

      {history.length > 1 && (
        <Card>
          <CardHeader>
            <CardTitle>历史简报</CardTitle>
          </CardHeader>
          <div className="space-y-1">
            {history.slice(1, 10).map((b) => (
              <button
                key={b.id}
                onClick={() => setCurrent(b)}
                className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm hover:bg-bg-subtle"
              >
                <span className="flex items-center gap-2">
                  <span className="text-muted">{fmtDate(b.created_at)}</span>
                  <span className="rounded bg-bg-subtle px-1.5 py-0.5 text-[10px] text-muted">
                    {b.model}
                  </span>
                </span>
                <ChevronRight size={14} className="text-muted" />
              </button>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
