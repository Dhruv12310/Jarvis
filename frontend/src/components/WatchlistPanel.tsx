// The user's public watch terms (symbols + topics). The backend stores only {kind, value} - no
// live price feed here, so rows show the term + a kind tag honestly (no invented numbers).
import type { Watch } from "../types";
import HudPanel from "./HudPanel";

export default function WatchlistPanel({ items }: { items: Watch[] }) {
  return (
    <HudPanel label="Watchlist" glow="arc">
      {items.length === 0 ? (
        <p style={{ color: "var(--text-low)", fontFamily: "var(--font-sans)", fontSize: 14, margin: 0 }}>
          Nothing watched yet.
        </p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {items.map((w) => (
            <div
              key={`${w.kind}:${w.value}`}
              style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}
            >
              <span
                className="tabular"
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 14,
                  color: w.kind === "symbol" ? "var(--arc-bright)" : "var(--text-hi)",
                }}
              >
                {w.value}
              </span>
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  fontWeight: 600,
                  letterSpacing: "0.12em",
                  textTransform: "uppercase",
                  color: "var(--text-low)",
                  border: "1px solid var(--arc-faint)",
                  borderRadius: 6,
                  padding: "1px 6px",
                }}
              >
                {w.kind}
              </span>
            </div>
          ))}
        </div>
      )}
    </HudPanel>
  );
}
