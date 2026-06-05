// One stock readout: mono ticker, large tabular price, signed delta (▲/▼, --up/--down), and a
// client-built sparkline. `history` is the rolling price series App accumulates from polls; below
// MIN_POINTS we render an honest baseline, never an invented curve. Remove-on-hover via onRemove.
import { useState } from "react";
import type { Quote } from "../types";
import Sparkline from "./Sparkline";

export const MIN_POINTS = 3; // need >=3 real samples before a sparkline tells the truth

interface Props {
  quote: Quote;
  history: number[]; // rolling recent prices for this symbol (oldest -> newest)
  onRemove?: (symbol: string) => void;
  onOpen?: (symbol: string) => void; // click the tile -> open the company-depth panel
}

const fmtPrice = (n: number) =>
  n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function StockTile({ quote, history, onRemove, onOpen }: Props) {
  const [hover, setHover] = useState(false);
  const up = quote.change >= 0;
  const color = up ? "var(--up)" : "var(--down)";
  const sparkClass = up ? "is-up" : "is-down";
  const ready = history.length >= MIN_POINTS;
  const open = onOpen ? () => onOpen(quote.symbol) : undefined;

  return (
    <div
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onClick={open}
      onKeyDown={open ? (e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), open()) : undefined}
      role={open ? "button" : undefined}
      tabIndex={open ? 0 : undefined}
      aria-label={open ? `Open ${quote.symbol} company detail` : undefined}
      className="hud-inset"
      style={{ position: "relative", display: "flex", flexDirection: "column", gap: 6, padding: "10px 12px", cursor: open ? "pointer" : "default" }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span
          className="tabular"
          style={{ fontFamily: "var(--font-mono)", fontSize: 13, letterSpacing: "0.06em", color: "var(--arc-bright)" }}
        >
          {quote.symbol}
        </span>
        {onRemove && hover && (
          <button
            onClick={(e) => {
              e.stopPropagation(); // removing must not also open the company panel
              onRemove(quote.symbol);
            }}
            aria-label={`Stop tracking ${quote.symbol}`}
            style={{
              background: "transparent",
              border: "none",
              cursor: "pointer",
              color: "var(--text-low)",
              fontFamily: "var(--font-mono)",
              fontSize: 13,
              lineHeight: 1,
              padding: "0 2px",
            }}
          >
            ✕
          </button>
        )}
      </div>

      <span
        className="tabular"
        style={{ fontFamily: "var(--font-mono)", fontWeight: 500, fontSize: 22, lineHeight: 1, color: "var(--text-hi)" }}
      >
        <span style={{ fontSize: 12, color: "var(--text-low)", marginRight: 3 }}>$</span>
        {fmtPrice(quote.price)}
      </span>

      <span className="tabular" style={{ fontFamily: "var(--font-mono)", fontSize: 12, color }}>
        {up ? "▲" : "▼"} {fmtPrice(Math.abs(quote.change))} ({up ? "+" : ""}
        {quote.change_pct.toFixed(2)}%)
      </span>

      {ready ? (
        <div className={`hud-spark ${sparkClass}`}>
          <Sparkline values={history} />
        </div>
      ) : (
        <div
          className="hud-spark"
          title="Building a short history from live polls…"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: "var(--font-mono)",
            fontSize: 9,
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            color: "var(--text-low)",
          }}
        >
          warming up… {history.length}/{MIN_POINTS}
        </div>
      )}
    </div>
  );
}
