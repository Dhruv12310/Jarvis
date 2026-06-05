// The cockpit wiring: holds the feed + side-rail state, owns the busy/online indicators, runs the
// light live-widget polls (quotes + goal-feed, OUTSIDE run() so they never strobe the busy LED), and
// binds the shortcut bar + chat input + FS modal to the controller (which shapes cards exactly like
// the Flet GUI). All capability logic lives behind the API in JarvisService; this only orchestrates.
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api";
import AppShell from "./components/AppShell";
import ChatInput from "./components/ChatInput";
import CompanyPanel from "./components/CompanyPanel";
import Feed from "./components/Feed";
import FsModal, { type FsMode } from "./components/FsModal";
import KindIcon from "./components/KindIcon";
import NavBar, { type View } from "./components/NavBar";
import NewsView from "./components/NewsView";
import ShortcutBar, { type ShortcutAction } from "./components/ShortcutBar";
import SidePanel from "./components/SidePanel";
import StatusBar from "./components/StatusBar";
import TickerTape from "./components/TickerTape";
import { makeController } from "./controller";
import type { CardData, Goal, GoalFeed, NewsItem, Quote, SystemHealth, Watch } from "./types";

const QUOTE_INTERVAL_MS = 15_000;
const GOALFEED_INTERVAL_MS = 120_000;
const NEWS_INTERVAL_MS = 300_000; // GDELT TTL is 900s; poll gently, only while News is open
const MAX_HISTORY = 30;
const SHOW_TICKER = true;

function stamp(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

const FILE_GLYPH = (
  <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6}>
    <path d="M13 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <path d="M13 3v5h5" />
  </svg>
);
const FOLDER_GLYPH = (
  <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6}>
    <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
  </svg>
);

export default function App() {
  const [cards, setCards] = useState<(CardData & { id: number; time: string })[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [online, setOnline] = useState(true);
  const [goals, setGoals] = useState<Goal[]>([]);
  const [watchlist, setWatchlist] = useState<Watch[]>([]);
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [quotesLoaded, setQuotesLoaded] = useState(false);
  const [history, setHistory] = useState<Record<string, number[]>>({});
  const [goalFeed, setGoalFeed] = useState<GoalFeed[]>([]);
  const [uptime, setUptime] = useState("00:00:00");
  const [topSuggestion, setTopSuggestion] = useState<{ content: string; why: string }>();
  const [fsMode, setFsMode] = useState<FsMode | null>(null);
  const [companySymbol, setCompanySymbol] = useState<string | null>(null);
  const [view, setView] = useState<View>("cockpit");
  const [news, setNews] = useState<NewsItem[]>([]);
  const [newsLoaded, setNewsLoaded] = useState(false);
  const idRef = useRef(0);
  const didInit = useRef(false);
  const mountAt = useRef(new Date().getTime());

  // Stable post(): append a card with a fresh id + arrival timestamp.
  const controller = useMemo(() => {
    const post = (card: CardData) =>
      setCards((prev) => [...prev, { ...card, id: idRef.current++, time: stamp() }]);
    return makeController(post);
  }, []);

  const refreshGoals = () => api.goals().then((r) => setGoals(r.goals)).catch(() => {});
  const refreshWatchlist = () =>
    api.watchlist().then((r) => setWatchlist(r.watchlist)).catch(() => {});
  const refreshGoalFeed = () => api.goalFeed().then((r) => setGoalFeed(r.feed)).catch(() => {});
  const refreshNews = () =>
    api.news().then((r) => setNews(r.items)).catch(() => {}).finally(() => setNewsLoaded(true));

  // Quote poll: NOT via run() (no busy/online strobe). Appends each price to the rolling per-symbol
  // history (capped) so sparklines build client-side from successive snapshots.
  const refreshQuotes = async () => {
    try {
      const { quotes: q } = await api.quotes(); // watchlist default
      setQuotes(q);
      setHistory((prev) => {
        const next: Record<string, number[]> = {};
        for (const { symbol, price } of q) {
          next[symbol] = [...(prev[symbol] ?? []), price].slice(-MAX_HISTORY);
        }
        return next; // drop history for symbols no longer watched
      });
      setOnline(true); // a good poll is evidence the link is up; never set false here
    } catch {
      /* transient: keep last good quotes; the link LED is owned by health/briefing */
    } finally {
      setQuotesLoaded(true);
    }
  };

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await fn();
      setOnline(true);
    } catch {
      setOnline(false);
    } finally {
      setBusy(false);
    }
  };

  // Power-on (guarded; must not run twice - it posts the briefing card).
  useEffect(() => {
    if (didInit.current) return;
    didInit.current = true;
    api.health().then(() => setOnline(true)).catch(() => setOnline(false));
    void run(() => controller.showBriefing());
    refreshGoals();
    refreshWatchlist();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Uptime ticker (1s).
  useEffect(() => {
    const id = window.setInterval(() => {
      const s = Math.floor((new Date().getTime() - mountAt.current) / 1000);
      const p = (n: number) => String(n).padStart(2, "0");
      setUptime(`${p(Math.floor(s / 3600))}:${p(Math.floor((s / 60) % 60))}:${p(s % 60)}`);
    }, 1000);
    return () => window.clearInterval(id);
  }, []);

  // Live-widget polls (own effects; visibility-aware; cleanup-safe). Never touch run()/busy.
  useEffect(() => {
    void refreshQuotes();
    const tick = () => document.visibilityState === "visible" && void refreshQuotes();
    const id = window.setInterval(tick, QUOTE_INTERVAL_MS);
    const onVis = () => document.visibilityState === "visible" && void refreshQuotes();
    document.addEventListener("visibilitychange", onVis);
    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", onVis);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    void refreshGoalFeed();
    const id = window.setInterval(
      () => document.visibilityState === "visible" && void refreshGoalFeed(),
      GOALFEED_INTERVAL_MS,
    );
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // News poll: only while the News view is open (avoid needless GDELT hits from the cockpit).
  useEffect(() => {
    if (view !== "news") return;
    void refreshNews();
    const id = window.setInterval(
      () => document.visibilityState === "visible" && void refreshNews(),
      NEWS_INTERVAL_MS,
    );
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view]);

  const send = () => {
    const text = input;
    if (!text.trim()) return;
    setInput("");
    void run(() => controller.ask(text));
  };

  const addGoalFromInput = () => {
    const text = input;
    if (!text.trim()) return;
    setInput("");
    void run(async () => {
      await controller.addGoal(text);
      await refreshGoals();
      refreshGoalFeed();
    });
  };

  const addGoalFromPanel = (text: string) =>
    run(async () => {
      await controller.addGoal(text);
      await refreshGoals();
      refreshGoalFeed();
    });

  const openSuggestions = () =>
    run(async () => {
      const list = await controller.showSuggestions();
      if (list[0]) setTopSuggestion({ content: list[0].content, why: list[0].why });
    });

  // "Track any company": resolve a typed name/ticker to a symbol (Finnhub /search), watch it, refresh
  // so the tile appears at once. Discrete user action -> run() (a spinner is appropriate here).
  const addTicker = (query: string) =>
    run(async () => {
      let symbol = query.trim().toUpperCase();
      try {
        const { matches } = await api.symbolSearch(query.trim());
        if (matches.length) symbol = matches[0].symbol;
      } catch {
        /* no search hit -> fall back to the raw uppercased text */
      }
      await api.addWatch("symbol", symbol);
      await refreshWatchlist();
      await refreshQuotes();
    });

  const removeTicker = (symbol: string) =>
    run(async () => {
      await api.removeWatch("symbol", symbol);
      await refreshWatchlist();
      await refreshQuotes();
    });

  const submitFs = (path: string, content: string) => {
    const mode = fsMode;
    setFsMode(null); // close immediately; the result lands as a feed card
    void run(() =>
      mode === "folder" ? controller.createFolder(path) : controller.createFile(path, content),
    );
  };

  const actions: ShortcutAction[] = [
    { id: "briefing", label: "Briefing", icon: <KindIcon kind="briefing" />, onClick: () => run(controller.showBriefing) },
    { id: "agenda", label: "Agenda", icon: <KindIcon kind="agenda" />, onClick: () => run(controller.showAgenda) },
    { id: "markets", label: "Markets / News", icon: <KindIcon kind="answer" />, onClick: () => run(controller.askMarketsNews) },
    { id: "finance", label: "Finance", icon: <KindIcon kind="finance" />, onClick: () => run(controller.showFinance) },
    { id: "goalfeed", label: "Goal Feed", icon: <KindIcon kind="suggestion" />, onClick: () => run(controller.showGoalFeed), accent: "gold" },
    { id: "goal", label: "Add Goal", icon: <KindIcon kind="goal" />, onClick: addGoalFromInput, accent: "gold" },
    { id: "suggest", label: "Suggestions", icon: <KindIcon kind="suggestion" />, onClick: openSuggestions, accent: "gold" },
    { id: "fs-file", label: "+ File", icon: FILE_GLYPH, onClick: () => setFsMode("file") },
    { id: "fs-folder", label: "+ Folder", icon: FOLDER_GLYPH, onClick: () => setFsMode("folder"), accent: "gold" },
  ];

  const systems: SystemHealth[] = [
    { id: "link", label: "link", state: online ? "ok" : "down" },
    { id: "markets", label: "mkt", state: quotes.length ? "ok" : "warn" },
    { id: "ai", label: "ai", state: online ? "ok" : "down" },
  ];

  return (
    <>
      <AppShell
        statusBar={
          <StatusBar
            systems={systems}
            busy={busy}
            alert={!online}
            uptime={uptime}
            nav={<NavBar view={view} onChange={setView} />}
          />
        }
        ticker={SHOW_TICKER ? <TickerTape quotes={quotes} /> : undefined}
        hideSide={view === "news"}
        feed={view === "cockpit" ? <Feed cards={cards} /> : <NewsView items={news} loading={!newsLoaded} />}
        side={
          <SidePanel
            goals={goals}
            watchlist={watchlist}
            quotes={quotes}
            history={history}
            quotesLoaded={quotesLoaded}
            goalFeed={goalFeed}
            topSuggestion={topSuggestion}
            onAddGoal={addGoalFromPanel}
            onAddTicker={addTicker}
            onRemoveTicker={removeTicker}
            onOpenSuggestions={openSuggestions}
            onOpenCompany={setCompanySymbol}
          />
        }
        dock={
          <div className="hud-glass" style={{ padding: 12, display: "flex", flexDirection: "column", gap: 10 }}>
            <ShortcutBar actions={actions} />
            <ChatInput value={input} onChange={setInput} onSubmit={send} busy={busy} />
          </div>
        }
      />
      <FsModal mode={fsMode} busy={busy} onSubmit={submitFs} onClose={() => setFsMode(null)} />
      <CompanyPanel symbol={companySymbol} onClose={() => setCompanySymbol(null)} />
    </>
  );
}
