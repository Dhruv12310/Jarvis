// Right rail: the denser live-widget stack. Top to bottom: live stock tiles (markets), watchlist,
// goals (owned), the goal-driven feed (goals -> relevant info), the next push nudge, then the
// Wave-2 weather + news slots (honest "offline" until their endpoints land).
import type { Goal, GoalFeed, Quote, Watch } from "../types";
import GoalFeedWidget from "./GoalFeedWidget";
import GoalsPanel from "./GoalsPanel";
import LiveStocksPanel from "./LiveStocksPanel";
import NextNudgeWidget from "./NextNudgeWidget";
import WatchlistPanel from "./WatchlistPanel";

interface Props {
  goals: Goal[];
  watchlist: Watch[];
  quotes: Quote[];
  history: Record<string, number[]>;
  quotesLoaded: boolean;
  goalFeed: GoalFeed[];
  topSuggestion?: { content: string; why: string };
  onAddGoal: (text: string) => void;
  onAddTicker: (query: string) => void;
  onRemoveTicker: (symbol: string) => void;
  onOpenSuggestions: () => void;
  onOpenCompany: (symbol: string) => void;
}

export default function SidePanel({
  goals,
  watchlist,
  quotes,
  history,
  quotesLoaded,
  goalFeed,
  topSuggestion,
  onAddGoal,
  onAddTicker,
  onRemoveTicker,
  onOpenSuggestions,
  onOpenCompany,
}: Props) {
  return (
    <div style={{ height: "100%", overflowY: "auto", display: "flex", flexDirection: "column", gap: 14, paddingRight: 2 }}>
      <LiveStocksPanel
        quotes={quotes}
        history={history}
        loaded={quotesLoaded}
        onAdd={onAddTicker}
        onRemove={onRemoveTicker}
        onOpen={onOpenCompany}
      />
      <WatchlistPanel items={watchlist} />
      <GoalsPanel goals={goals} onAdd={onAddGoal} />
      <GoalFeedWidget feed={goalFeed} />
      <NextNudgeWidget top={topSuggestion} onOpen={onOpenSuggestions} />
    </div>
  );
}
