import { useEffect, useRef, useState } from "react";
import { MessageSquare, Send, Trash2, Sparkles } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "../lib/api";
import { Button, Card } from "../components/ui";
import { cn } from "../lib/utils";

interface Msg {
  id: number;
  role: string;
  content: string;
  created_at?: string;
}

const SUGGESTIONS = [
  "QQQ 今天为什么涨跌？",
  "VOO 和 QQQ 哪个更适合长期定投？",
  "我的持仓现在整体风险怎么样？",
  "什么是 ETF 的费率？越低越好吗？",
];

export default function Chat() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.chatHistory().then((m) => setMessages(m || [])).catch(() => {});
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  async function send(text?: string) {
    const q = (text ?? input).trim();
    if (!q || loading) return;
    setInput("");
    const userMsg: Msg = { id: Date.now(), role: "user", content: q };
    setMessages((m) => [...m, userMsg]);
    setLoading(true);
    try {
      const r = await api.askChat(q);
      setMessages((m) => [...m, { id: r.id, role: "assistant", content: r.content, created_at: r.created_at }]);
    } catch (err: any) {
      setMessages((m) => [...m, { id: Date.now() + 1, role: "assistant", content: `⚠️ ${err.message}` }]);
    } finally {
      setLoading(false);
    }
  }

  async function clear() {
    if (!confirm("清空所有对话记录？")) return;
    await api.clearChat();
    setMessages([]);
  }

  return (
    <div className="flex h-[calc(100vh-3rem)] flex-col md:h-[calc(100vh-2rem)]">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-semibold">
            <MessageSquare size={20} className="text-brand" /> AI 投资问答
          </h1>
          <p className="text-sm text-muted">基于你的持仓和实时数据，问任何美股问题</p>
        </div>
        {messages.length > 0 && (
          <Button onClick={clear} variant="ghost" size="sm">
            <Trash2 size={14} /> 清空
          </Button>
        )}
      </div>

      <Card className="flex min-h-0 flex-1 flex-col p-0">
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-4">
          {messages.length === 0 && !loading ? (
            <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-brand/10 text-brand">
                <Sparkles size={26} />
              </div>
              <div>
                <h3 className="font-medium">问我任何美股问题</h3>
                <p className="mt-1 text-sm text-muted">
                  我会结合你的持仓和最新市场数据来回答
                </p>
              </div>
              <div className="flex flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => send(s)}
                    className="rounded-full border border-border bg-bg-subtle px-3 py-1.5 text-xs text-slate-300 transition-colors hover:border-brand/40 hover:text-brand-light"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {messages.map((m) => (
                <div key={m.id} className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}>
                  <div
                    className={cn(
                      "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm",
                      m.role === "user"
                        ? "bg-brand text-white"
                        : "bg-bg-subtle text-slate-100"
                    )}
                  >
                    {m.role === "assistant" ? (
                      <div className="prose-briefing">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                      </div>
                    ) : (
                      <span className="whitespace-pre-wrap">{m.content}</span>
                    )}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="flex justify-start">
                  <div className="flex items-center gap-1.5 rounded-2xl bg-bg-subtle px-4 py-3">
                    {[0, 1, 2].map((i) => (
                      <span
                        key={i}
                        className="h-2 w-2 animate-bounce rounded-full bg-muted"
                        style={{ animationDelay: `${i * 150}ms` }}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="border-t border-border p-3">
          <div className="flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()}
              placeholder="输入你的问题，按 Enter 发送…"
              className="h-11 flex-1 rounded-lg border border-border bg-bg px-4 text-sm text-slate-100 placeholder:text-muted focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/30"
              disabled={loading}
            />
            <Button onClick={() => send()} loading={loading} size="lg" className="!h-11 !px-5">
              {!loading && <Send size={16} />}
            </Button>
          </div>
          <p className="mt-1.5 text-center text-[11px] text-muted">
            AI 回答仅供参考，不构成投资建议 · 回答基于你的持仓和最新数据
          </p>
        </div>
      </Card>
    </div>
  );
}
