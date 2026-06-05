// Thin fetch client over the FastAPI seam. Uses a relative /api base so it works identically in
// dev (Vite proxies to `python -m jarvis serve`) and prod (FastAPI serves this app same-origin).
// Errors arrive already REDACTED from the backend (jarvis/api/app.py) - we surface that text as-is.
import type {
  Account,
  AgendaResult,
  AskResult,
  BudgetStatus,
  CompanyView,
  DeepDiveResult,
  FsListResult,
  FsResult,
  Goal,
  GoalFeed,
  NewsItem,
  Quote,
  Suggestion,
  SymbolMatch,
  Watch,
} from "./types";

const BASE = "/api";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function authHeader(): Record<string, string> {
  const t = localStorage.getItem("jarvis_token");
  return t ? { "X-Jarvis-Token": t } : {};
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(BASE + path, {
      ...init,
      headers: { "Content-Type": "application/json", ...authHeader(), ...init?.headers },
    });
  } catch {
    // network/transport failure (server not running) - keep the message generic + actionable.
    throw new ApiError("Cannot reach Jarvis. Is `python -m jarvis serve` running?", 0);
  }
  if (!res.ok) {
    let detail = res.statusText || `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body && typeof body.error === "string") detail = body.error;
    } catch {
      /* non-JSON error body - fall back to status text */
    }
    throw new ApiError(detail, res.status);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const post = (body?: unknown): RequestInit => ({
  method: "POST",
  body: body === undefined ? undefined : JSON.stringify(body),
});

export const api = {
  health: () => req<{ status: string; name: string; source: string }>("/health"),
  briefing: () => req<{ text: string }>("/briefing"),
  ask: (text: string) => req<AskResult>("/ask", post({ text })),
  agenda: () => req<AgendaResult>("/agenda"),
  financeAsk: (question: string) => req<{ text: string }>("/finance/ask", post({ question })),
  budgets: () => req<{ budgets: BudgetStatus[] }>("/finance/budgets"),
  accounts: () => req<{ accounts: Account[] }>("/finance/accounts"),
  goals: () => req<{ goals: Goal[] }>("/goals"),
  addGoal: (text: string) => req<Goal>("/goals", post({ text })),
  completeGoal: (id: number) => req<Goal>(`/goals/${id}/complete`, post()),
  watchlist: () => req<{ watchlist: Watch[] }>("/watchlist"),
  addWatch: (kind: string, value: string) => req<Watch>("/watch", post({ kind, value })),
  removeWatch: (kind: string, value: string) =>
    req<{ ok: boolean }>("/watch/remove", post({ kind, value })),
  suggestions: () => req<{ suggestions: Suggestion[] }>("/suggestions"),

  // Live market quotes (watchlist default, or an ad-hoc ?symbols=NVDA,AMD grid). Pure read.
  quotes: (symbols?: string[]) =>
    req<{ quotes: Quote[] }>(
      "/quotes" +
        (symbols && symbols.length ? `?symbols=${encodeURIComponent(symbols.join(","))}` : ""),
    ),
  // Resolve a typed company name/ticker to candidate symbols ("track any company" by name).
  symbolSearch: (q: string) =>
    req<{ matches: SymbolMatch[] }>(`/symbol-search?q=${encodeURIComponent(q)}`),
  // The goal-driven PULL feed: per active goal, deterministic relevant info with a WHY.
  goalFeed: () => req<{ feed: GoalFeed[] }>("/goal-feed"),

  // Filesystem (cockpit shortcut bar) — full-disk reach; POSTs gated by the off-loopback guard.
  createFile: (path: string, content = "", overwrite = false) =>
    req<FsResult>("/fs/file", post({ path, content, overwrite })),
  createFolder: (path: string) => req<FsResult>("/fs/folder", post({ path })),
  listDir: (path?: string) =>
    req<FsListResult>(`/fs/list${path ? `?path=${encodeURIComponent(path)}` : ""}`),

  // Company depth (fundamentals/metrics/analyst/news). Pure read; accepts a symbol or a name.
  company: (symbol: string) => req<CompanyView>(`/company/${encodeURIComponent(symbol)}`),
  // Tier-2 cloud Deep Dive — SPENDS Anthropic tokens; call only behind an explicit confirm.
  companyDeepdive: (symbol: string) =>
    req<DeepDiveResult>(`/company/${encodeURIComponent(symbol)}/deepdive`, post()),
  // World news for the News view + globe (GDELT keyless + GNews).
  news: (q?: string) =>
    req<{ items: NewsItem[] }>("/news" + (q ? `?q=${encodeURIComponent(q)}` : "")),
};
