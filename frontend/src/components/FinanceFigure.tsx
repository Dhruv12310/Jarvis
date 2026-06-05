// Renders the finance answer: a leading currency figure shown large in mono tabular-nums, colored
// by sign, with the remaining prose in Inter. Falls back to plain prose when no figure is found.
import MarkdownBody from "./MarkdownBody";

// First currency-looking figure in the sentence, e.g. "$42.50", "-$1,200", "$3.4k".
const MONEY = /(-?\$[\d,]+(?:\.\d+)?[kKmM]?)/;

export default function FinanceFigure({ body }: { body: string }) {
  const m = MONEY.exec(body);
  if (!m) return <MarkdownBody source={body} />;

  const figure = m[1];
  const negative = figure.trim().startsWith("-");
  const color = negative ? "var(--danger)" : "var(--ok)";
  const before = body.slice(0, m.index).trim();
  const after = body.slice(m.index + figure.length).trim();

  return (
    <div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
        <span style={{ color }} aria-hidden>
          {negative ? "▼" : "▲"}
        </span>
        <span
          className="tabular"
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 28,
            fontWeight: 500,
            color,
            letterSpacing: "0.01em",
          }}
        >
          {figure}
        </span>
      </div>
      {(before || after) && (
        <div className="prose-hud" style={{ marginTop: 6, color: "var(--text-mid)" }}>
          {[before, after].filter(Boolean).join(" … ")}
        </div>
      )}
    </div>
  );
}
