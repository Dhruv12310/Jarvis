// The goal-driven PULL feed: per active goal, the public info Jarvis surfaced for it, each with a
// deterministic WHY. Calm by design - it informs, it does not push, so no glow. Gold live dot when
// any goal has relevant info. Capped server-side. This is what makes goals visibly drive the feed.
import type { GoalFeed } from "../types";
import HudPanel from "./HudPanel";

const KIND_COLOR: Record<string, string> = {
  market: "var(--arc-bright)",
  news: "var(--text-hi)",
  story: "var(--text-hi)",
  snippet: "var(--teal)",
  suggestion: "var(--gold)",
};

export default function GoalFeedWidget({ feed }: { feed: GoalFeed[] }) {
  const withItems = feed.filter((f) => f.items.length > 0);
  const hasAny = withItems.length > 0;
  return (
    <HudPanel label="Goal Feed" reticle live={hasAny} liveColor="var(--gold)">
      {!hasAny ? (
        <p style={{ color: "var(--text-low)", fontFamily: "var(--font-sans)", fontSize: 13, margin: 0 }}>
          No goal-relevant info right now.
        </p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {withItems.map((f) => (
            <div key={f.goal_id}>
              <div
                className="tabular"
                style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--gold)", marginBottom: 6 }}
              >
                #{f.goal_id} {f.goal}
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {f.items.map((it, i) => (
                  <div key={`${it.source}:${it.url ?? it.title}:${i}`} style={{ display: "flex", gap: 8 }}>
                    <span className="chip" style={{ color: KIND_COLOR[it.kind] ?? "var(--text-low)", flexShrink: 0 }}>
                      {it.kind}
                    </span>
                    <div style={{ minWidth: 0 }}>
                      {it.url ? (
                        <a
                          href={it.url}
                          target="_blank"
                          rel="noreferrer"
                          style={{ color: "var(--text-hi)", fontFamily: "var(--font-sans)", fontSize: 13, textDecoration: "none" }}
                        >
                          {it.title}
                        </a>
                      ) : (
                        <span style={{ color: "var(--text-hi)", fontFamily: "var(--font-sans)", fontSize: 13 }}>
                          {it.title}
                        </span>
                      )}
                      <p
                        style={{
                          margin: "2px 0 0",
                          color: "var(--text-mid)",
                          fontFamily: "var(--font-sans)",
                          fontSize: 12,
                          lineHeight: 1.45,
                          display: "-webkit-box",
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: "vertical",
                          overflow: "hidden",
                        }}
                      >
                        {it.detail}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </HudPanel>
  );
}
