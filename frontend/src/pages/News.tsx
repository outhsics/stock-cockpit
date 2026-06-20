import { useCallback, useEffect, useState } from "react";
import { RefreshCw, ExternalLink, Newspaper, Languages, Check } from "lucide-react";
import { api } from "../lib/api";
import { Button, Card } from "../components/ui";
import { cn, fmtDate } from "../lib/utils";

type LangFilter = "all" | "cn" | "en";

export default function News() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [translating, setTranslating] = useState(false);
  const [lang, setLang] = useState<LangFilter>("all");
  const [symbolFilter, setSymbolFilter] = useState<string | null>(null);
  const [symbols, setSymbols] = useState<string[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.news(symbolFilter || undefined, 60, lang === "all" ? undefined : lang);
      setItems(res.items || []);
      if (symbols.length === 0) {
        const h = await api.holdings().catch(() => []);
        setSymbols(h.map((x: any) => x.symbol));
      }
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbolFilter, lang]);

  useEffect(() => {
    load();
  }, [load]);

  async function refresh() {
    setRefreshing(true);
    try {
      await api.refreshNews();
      await load();
    } finally {
      setRefreshing(false);
    }
  }

  async function translate() {
    setTranslating(true);
    try {
      await api.translateNews(20);
      await load();
    } finally {
      setTranslating(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-semibold">
            <Newspaper size={20} className="text-brand" /> 财经新闻
          </h1>
          <p className="text-sm text-muted">中文财经源 + 英文源（可一键翻译成中文）</p>
        </div>
        <div className="flex gap-2">
          <Button onClick={translate} loading={translating} variant="secondary" size="sm">
            {!translating && <Languages size={14} />} 翻译成中文
          </Button>
          <Button onClick={refresh} loading={refreshing} variant="secondary" size="sm">
            {!refreshing && <RefreshCw size={14} />} 刷新
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {([["all", "全部"], ["cn", "中文"], ["en", "英文"]] as const).map(([val, label]) => (
          <button
            key={val}
            onClick={() => setLang(val)}
            className={cn(
              "rounded-full px-3 py-1 text-xs transition-colors",
              lang === val ? "bg-brand text-white" : "bg-bg-card text-muted hover:text-slate-100"
            )}
          >
            {label}
          </button>
        ))}
        {symbols.length > 0 && (
          <>
            <span className="mx-1 text-muted">|</span>
            <button
              onClick={() => setSymbolFilter(null)}
              className={cn(
                "rounded-full px-3 py-1 text-xs transition-colors",
                !symbolFilter ? "bg-brand text-white" : "bg-bg-card text-muted hover:text-slate-100"
              )}
            >
              我的持仓
            </button>
            {symbols.map((s) => (
              <button
                key={s}
                onClick={() => setSymbolFilter(symbolFilter === s ? null : s)}
                className={cn(
                  "rounded-full px-3 py-1 text-xs transition-colors",
                  symbolFilter === s ? "bg-brand text-white" : "bg-bg-card text-muted hover:text-slate-100"
                )}
              >
                {s}
              </button>
            ))}
          </>
        )}
      </div>

      {loading ? (
        <div className="flex h-40 items-center justify-center text-muted">加载中…</div>
      ) : items.length === 0 ? (
        <Card className="flex flex-col items-center gap-3 py-12 text-center">
          <div className="text-muted">暂无新闻</div>
          <p className="text-sm text-muted">点击「刷新」抓取最新新闻。中文源来自财联社/华尔街见闻/金十。</p>
        </Card>
      ) : (
        <div className="space-y-2">
          {items.map((n) => {
            const isCN = /[\u4e00-\u9fff]/.test(n.title) || /财联社|华尔街见闻|金十|中文/.test(n.source);
            return (
              <a
                key={n.id}
                href={n.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block rounded-xl border border-border bg-bg-card p-4 transition-colors hover:border-brand/40 hover:bg-bg-subtle/40"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
                      {n.symbol && (
                        <span className="rounded bg-brand/15 px-1.5 py-0.5 font-medium text-brand-light">
                          {n.symbol}
                        </span>
                      )}
                      <span>{n.source}</span>
                      <span>·</span>
                      <span>{fmtDate(n.published_at)}</span>
                      {isCN && (
                        <span className="flex items-center gap-0.5 rounded bg-pos/15 px-1.5 py-0.5 text-[10px] text-pos">
                          <Check size={9} /> 中文
                        </span>
                      )}
                    </div>
                    <h3 className="mt-1.5 font-medium leading-snug text-slate-100">{n.title}</h3>
                    {n.summary && (
                      <p className="mt-1 line-clamp-2 text-xs text-muted">
                        {n.summary.replace(/<[^>]+>/g, "").slice(0, 180)}
                      </p>
                    )}
                  </div>
                  <ExternalLink size={14} className="mt-1 shrink-0 text-muted" />
                </div>
              </a>
            );
          })}
        </div>
      )}
    </div>
  );
}

