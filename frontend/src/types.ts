// Shapes mirroring the JSON the FastAPI seam returns (jarvis/api/serialize.py).
// datetimes arrive as ISO strings; Decimals as exact strings.

export type CardKind =
  | "briefing"
  | "answer"
  | "chat"
  | "agenda"
  | "goal"
  | "finance"
  | "suggestion"
  | "error";

export interface CardData {
  title: string;
  body: string;
  kind: CardKind;
  why?: string | null;
}

export interface AskResult {
  text: string;
  grounded: boolean;
  cached: boolean;
}

export interface CalendarEvent {
  id: string;
  summary: string;
  start: string; // ISO datetime (tz-aware)
  end: string;
  location: string | null;
  all_day: boolean;
}

export interface AgendaResult {
  events: CalendarEvent[];
  connected: boolean;
}

export interface Goal {
  id: number;
  description: string;
  status: string; // active | done
  progress: number; // 0..1
  priority: string; // low | medium | high
  deadline: string | null;
  created_at: string;
}

export interface Watch {
  kind: string; // symbol | topic
  value: string;
}

export interface Suggestion {
  id: string;
  created_at: string;
  candidate_type: string;
  entity_key: string;
  content: string;
  why: string;
  source_ids: string[];
  topics: string[];
  features: Record<string, number>;
  score: number;
  surfaced: boolean;
  channel: string;
}

export interface Account {
  id: string;
  name: string;
  type: string;
  balance: string; // Decimal as exact string
}

export interface BudgetStatus {
  category: string;
  limit: string;
  actual: string;
  remaining: string;
  over: boolean;
}

// --- Live market quotes (GET /api/quotes -> {quotes: Quote[]}) -------------------------------
export interface Quote {
  symbol: string;
  price: number;
  change: number; // absolute: price - prev_close (computed server-side)
  change_pct: number;
  prev_close: number;
  currency: string; // "USD"
}

// --- Symbol search ("track any company" by name; GET /api/symbol-search?q=) ------------------
export interface SymbolMatch {
  symbol: string;
  description: string;
}

// --- Goal-driven PULL feed (GET /api/goal-feed -> {feed: GoalFeed[]}) ------------------------
export interface GoalFeedItem {
  title: string;
  detail: string;
  why: string; // deterministic "relates to goal #N: …"
  source: "markets" | "news" | "hn" | "knowledge" | "suggestion";
  kind: "market" | "news" | "story" | "snippet" | "suggestion";
  url: string | null;
}
export interface GoalFeed {
  goal_id: number;
  goal: string;
  items: GoalFeedItem[];
}

// --- Filesystem ops (cockpit shortcut bar) — mirrors jarvis/fs_ops.py dict shapes -----------
export interface FsResult {
  path: string; // resolved absolute path, already home-dir REDACTED by the API boundary
  kind: "file" | "folder";
  created: boolean;
  bytes?: number; // present for files only (UTF-8 byte length)
}
export interface FsEntry {
  name: string;
  kind: "file" | "folder";
}
export interface FsListResult {
  path: string; // base dir listed (redacted)
  entries: FsEntry[];
}

// --- Company depth (GET /api/company/{symbol}) ----------------------------------------------
export interface CompanyNews {
  title: string;
  source: string;
  url: string | null;
}
export interface CompanyView {
  symbol: string;
  name: string | null;
  industry: string | null;
  exchange: string | null;
  market_cap: string | null; // human-formatted, e.g. "$4.58T"
  ipo: string | null;
  weburl: string | null;
  metrics: Record<string, number | null> | null; // only populated keys present
  recommendation: string | null; // one-line analyst summary
  news: CompanyNews[];
  sources: string[];
  note: string | null; // set when no data / no key — render honestly
}
// POST /api/company/{symbol}/deepdive — Tier-2 cloud (Anthropic) synthesis. SPENDS tokens.
export interface DeepDiveResult {
  symbol: string;
  report: string | null; // markdown; null when disabled/failed
  note: string | null; // explains a null report (e.g. "set ANTHROPIC_API_KEY")
  escalated: boolean;
}

// --- World news (GET /api/news -> {items: NewsItem[]}) for the News view + globe ------------
export interface NewsItem {
  title: string;
  source: string;
  url: string | null;
  country: string | null; // GDELT full name; null -> no globe pin
  published: string | null;
  image: string | null;
}

export type SystemState = "ok" | "warn" | "down";
export interface SystemHealth {
  id: string;
  label: string;
  state: SystemState;
}
