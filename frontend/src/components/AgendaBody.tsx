// Parses the controller's agenda lines ("- HH:MM-HH:MM summary @ loc" / "- all day summary") into
// a mono time column + Inter summary with a small reticle dot. Handles the literal special states.
interface Row {
  time: string;
  summary: string;
}

function parse(body: string): Row[] | null {
  const lines = body.split("\n").filter((l) => l.startsWith("- "));
  if (lines.length === 0) return null;
  return lines.map((line) => {
    const rest = line.slice(2);
    // Match the timed prefix FIRST so a timed event titled e.g. "all day sync" isn't mis-split.
    const timed = /^(\d{2}:\d{2}-\d{2}:\d{2})\s+(.*)$/.exec(rest);
    if (timed) return { time: timed[1], summary: timed[2] };
    if (rest.startsWith("all day ")) return { time: "all day", summary: rest.slice("all day ".length) };
    return { time: "", summary: rest };
  });
}

export default function AgendaBody({ body }: { body: string }) {
  const rows = parse(body);
  if (!rows) {
    // not-connected / "No events today." - render the literal message as calm prose.
    return (
      <div className="prose-hud" style={{ color: "var(--text-mid)" }}>
        {body}
      </div>
    );
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {rows.map((r, i) => (
        <div key={i} style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              border: "1.5px solid var(--arc)",
              flexShrink: 0,
              alignSelf: "center",
            }}
          />
          <span
            className="tabular"
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 13,
              color: "var(--arc-bright)",
              minWidth: 96,
              flexShrink: 0,
            }}
          >
            {r.time}
          </span>
          <span style={{ fontFamily: "var(--font-sans)", fontSize: 15, color: "var(--text-hi)" }}>
            {r.summary}
          </span>
        </div>
      ))}
    </div>
  );
}
