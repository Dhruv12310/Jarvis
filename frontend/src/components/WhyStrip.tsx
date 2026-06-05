// The explainability contract for suggestion cards (the legacy Flet view dropped it; the design
// restores it). Gold-tinted inset well: a "WHY" caption + the deterministic reason.
export default function WhyStrip({ why }: { why: string }) {
  return (
    <div
      className="hud-inset"
      style={{
        marginTop: 12,
        padding: "8px 12px",
        borderColor: "var(--gold-faint)",
        background: "var(--gold-faint)",
        display: "flex",
        gap: 10,
        alignItems: "baseline",
      }}
    >
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: "0.14em",
          textTransform: "uppercase",
          color: "var(--gold)",
          flexShrink: 0,
        }}
      >
        Why
      </span>
      <span style={{ fontFamily: "var(--font-sans)", fontSize: 13, color: "var(--text-mid)" }}>
        {why}
      </span>
    </div>
  );
}
