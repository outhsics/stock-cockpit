// Lightweight API client. Token persisted in localStorage.
const BASE = "/api";

function getToken(): string | null {
  return localStorage.getItem("cockpit_token");
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem("cockpit_token", token);
  else localStorage.removeItem("cockpit_token");
}

export function isLoggedIn(): boolean {
  return !!getToken();
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const resp = await fetch(`${BASE}${path}`, { ...options, headers });

  if (resp.status === 401) {
    // Unauthorized: clear token, force re-login.
    setToken(null);
    if (window.location.pathname !== "/login") {
      window.location.href = "/login";
    }
    throw new Error("Unauthorized");
  }
  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`;
    try {
      const body = await resp.json();
      detail = body.detail || body.message || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (resp.status === 204) return undefined as T;
  return resp.json();
}

// ---- Auth ----
export const api = {
  login: (username: string, password: string) =>
    request<{ access_token: string; username: string }>("/auth/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ username, password }).toString(),
    }),
  register: (username: string, password: string) =>
    request<{ access_token: string; username: string }>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  me: () => request<{ id: number; username: string }>("/auth/me"),

  // ---- Portfolio ----
  overview: () => request<any>("/portfolio/overview"),
  holdings: () => request<any[]>("/portfolio/holdings"),
  addHolding: (body: { symbol: string; shares: number; cost_basis: number; note?: string }) =>
    request<any>("/portfolio/holdings", { method: "POST", body: JSON.stringify(body) }),
  updateHolding: (id: number, body: any) =>
    request<any>(`/portfolio/holdings/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteHolding: (id: number) =>
    request<any>(`/portfolio/holdings/${id}`, { method: "DELETE" }),
  refreshPrices: () => request<any>("/portfolio/refresh", { method: "POST" }),
  history: (period = "1y") => request<any>(`/portfolio/history?period=${period}`),

  // ---- Market ----
  quote: (symbol: string) => request<any>(`/market/quote/${symbol}`),
  info: (symbol: string) => request<any>(`/market/info/${symbol}`),
  marketHistory: (symbol: string, period = "1y") =>
    request<any>(`/market/history/${symbol}?period=${period}`),

  // ---- News ----
  news: (symbol?: string, limit = 50, lang?: string) => {
    const params = new URLSearchParams();
    if (symbol) params.set("symbol", symbol);
    if (lang) params.set("lang", lang);
    params.set("limit", String(limit));
    return request<any>(`/news?${params.toString()}`);
  },
  refreshNews: () => request<any>("/news/refresh", { method: "POST" }),
  translateNews: (limit = 20) =>
    request<any>("/news/translate", { method: "POST", body: JSON.stringify({ limit }) }),

  // ---- Briefing ----
  latestBriefing: () => request<any>("/briefing/latest"),
  listBriefings: (limit = 10) => request<any[]>(`/briefing/list?limit=${limit}`),
  generateBriefing: () =>
    request<any>("/briefing/generate", { method: "POST" }),

  // ---- AI Chat ----
  askChat: (question: string) =>
    request<any>("/chat/ask", { method: "POST", body: JSON.stringify({ question }) }),
  chatHistory: (limit = 50) => request<any[]>(`/chat/history?limit=${limit}`),
  clearChat: () => request<any>("/chat/history", { method: "DELETE" }),

  // ---- Congress / insider trades ----
  congress: (symbol?: string, limit = 50) =>
    request<any>(`/congress${symbol ? `?symbol=${symbol}` : ""}${symbol ? "&" : "?"}limit=${limit}`),
  refreshCongress: () => request<any>("/congress/refresh", { method: "POST" }),

  // ---- Deep research ----
  fundamentals: (symbol: string) => request<any>(`/research/fundamentals/${symbol}`),
  performance: (symbol: string, periods = "1mo,3mo,6mo,1y") =>
    request<any>(`/research/performance/${symbol}?periods=${periods}`),
  compare: (symbols: string[]) =>
    request<any>("/research/compare", { method: "POST", body: JSON.stringify({ symbols }) }),
  macro: () => request<any>("/research/macro"),
  earnings: () => request<any>("/research/earnings"),

  health: () => request<any>("/health"),
};
