// Single polymorphic card; dispatches on `kind`. Built on .hud-glass + a crisp 2px per-kind left
// rule (.card-rail). Header is a technical log row: kind glyph + uppercase mono title + timestamp.
import type { CardData } from "../types";
import AgendaBody from "./AgendaBody";
import FinanceFigure from "./FinanceFigure";
import KindIcon, { railColor } from "./KindIcon";
import MarkdownBody from "./MarkdownBody";
import WhyStrip from "./WhyStrip";

function Body({ card }: { card: CardData }) {
  switch (card.kind) {
    case "agenda":
      return <AgendaBody body={card.body} />;
    case "finance":
      return <FinanceFigure body={card.body} />;
    case "goal":
      return (
        <div className="prose-hud" style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
          <span style={{ color: "var(--gold)", fontFamily: "var(--font-mono)" }}>{card.body}</span>
        </div>
      );
    case "error":
      return (
        <div className="prose-hud" style={{ color: "var(--danger)", fontFamily: "var(--font-mono)", fontSize: 13 }}>
          {card.body}
        </div>
      );
    case "suggestion":
      return (
        <>
          <MarkdownBody source={card.body} />
          {card.why ? <WhyStrip why={card.why} /> : null}
        </>
      );
    default:
      return <MarkdownBody source={card.body} />;
  }
}

// Finance cards color the spine by sign (red on a negative figure, green otherwise) per the spec.
function cardRail(card: CardData): string {
  if (card.kind === "finance" && /-\s*\$[\d,]/.test(card.body)) return "var(--danger)";
  return railColor(card.kind);
}

export default function Card({ card, time }: { card: CardData; time: string }) {
  const rail = cardRail(card);
  return (
    <div
      className="hud-glass card-rail"
      style={{ ["--rail" as string]: rail, padding: "10px 14px 12px 16px" } as React.CSSProperties}
    >
      <header style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 7 }}>
        <KindIcon kind={card.kind} size={14} />
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 11.5,
            fontWeight: 500,
            letterSpacing: "0.09em",
            textTransform: "uppercase",
            color: "var(--text-hi)",
            flex: 1,
          }}
        >
          {card.title}
        </span>
        <span
          className="tabular"
          style={{ fontFamily: "var(--font-mono)", fontSize: 10.5, color: "var(--text-low)" }}
        >
          {time}
        </span>
      </header>
      <Body card={card} />
    </div>
  );
}
