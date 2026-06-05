// Optional top marquee: every quoted symbol scrolling once across, mono + tabular, edges fading into
// the frame. Uses the theme's .hud-ticker CSS (pure-CSS keyframe; reduced-motion freezes it). Items
// are DUPLICATED so the -50% translate loops seamlessly. Toggle by not rendering it.
import type { Quote } from "../types";

function Item({ q }: { q: Quote }) {
  const up = q.change >= 0;
  return (
    <span className="hud-ticker-item">
      <span className="sym">{q.symbol}</span>
      <span className={up ? "up" : "down"}>
        {up ? "▲" : "▼"} {q.change_pct.toFixed(2)}%
      </span>
    </span>
  );
}

export default function TickerTape({ quotes }: { quotes: Quote[] }) {
  if (quotes.length === 0) return null;
  return (
    <div className="hud-ticker hud-glass" style={{ height: 26, padding: "0 2px", marginTop: 8 }}>
      <div className="hud-ticker-track">
        {quotes.map((q) => (
          <Item key={`a-${q.symbol}`} q={q} />
        ))}
        {quotes.map((q) => (
          <Item key={`b-${q.symbol}`} q={q} />
        ))}
      </div>
    </div>
  );
}
