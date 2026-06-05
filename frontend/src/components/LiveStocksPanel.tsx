// Live stocks: a grid of StockTiles fed by GET /api/quotes (watchlist default), an add-ticker input
// doing the "track any company" loop (resolve name->symbol via /api/symbol-search, then addWatch),
// and remove-on-hover. `history` is owned by App (survives poll ticks) and threaded in. Empty +
// no-data states are honest: we never show a number the server didn't return.
import { useState } from "react";
import type { Quote } from "../types";
import HudPanel from "./HudPanel";
import StockTile from "./StockTile";

interface Props {
  quotes: Quote[];
  history: Record<string, number[]>;
  loaded: boolean; // has at least one /api/quotes call completed?
  onAdd: (query: string) => void; // App: symbol-search -> addWatch('symbol', T) -> refresh
  onRemove: (symbol: string) => void; // App: removeWatch('symbol', T) -> refresh
  onOpen?: (symbol: string) => void; // click a tile -> open the company-depth panel
}

export default function LiveStocksPanel({ quotes, history, loaded, onAdd, onRemove, onOpen }: Props) {
  const [text, setText] = useState("");

  const submit = () => {
    const t = text.trim();
    if (!t) return;
    onAdd(t);
    setText("");
  };

  return (
    <HudPanel label="Live Stocks" glow="arc" reticle live={quotes.length > 0}>
      {quotes.length === 0 ? (
        <p style={{ color: "var(--text-low)", fontFamily: "var(--font-sans)", fontSize: 14, margin: 0 }}>
          {loaded
            ? "No live quotes yet. Add a company below (name or ticker)."
            : "Loading quotes…"}
        </p>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 10 }}>
          {quotes.map((q) => (
            <StockTile key={q.symbol} quote={q} history={history[q.symbol] ?? []} onRemove={onRemove} onOpen={onOpen} />
          ))}
        </div>
      )}

      <div className="hud-inset" style={{ marginTop: 12, display: "flex", padding: 4 }}>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder="Track a company (e.g. Apple or AMD)…"
          style={{
            flex: 1,
            background: "transparent",
            border: "none",
            outline: "none",
            color: "var(--text-hi)",
            fontFamily: "var(--font-mono)",
            fontSize: 13,
            letterSpacing: "0.04em",
            padding: "6px 8px",
          }}
        />
        <button
          onClick={submit}
          aria-label="Track company"
          style={{ background: "transparent", border: "none", color: "var(--arc)", cursor: "pointer", fontSize: 18, padding: "0 8px" }}
        >
          +
        </button>
      </div>
    </HudPanel>
  );
}
