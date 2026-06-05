// The News view: the 3D globe (left) + a mono headline list (right) on one framed instrument panel.
// Pins/headlines link out to the article. Honest empty/loading states (GDELT rate-limits -> empty).
import { lazy, Suspense } from "react";
import type { NewsItem } from "../types";
import type { GlobePoint } from "./NewsGlobe";

// Lazy-load the globe (three.js is heavy) so it only costs bytes when the News view is opened.
const NewsGlobe = lazy(() => import("./NewsGlobe"));

export default function NewsView({ items, loading }: { items: NewsItem[]; loading: boolean }) {
  const openPoint = (p: GlobePoint) => {
    if (p.url) window.open(p.url, "_blank", "noopener");
  };
  return (
    <div
      className="hud-glass hud-reticle"
      style={{
        position: "relative",
        height: "100%",
        display: "grid",
        gridTemplateColumns: "minmax(0, 3fr) minmax(260px, 2fr)",
        overflow: "hidden",
      }}
    >
      <span className="hud-reticle-x" aria-hidden />

      <div style={{ position: "relative", minHeight: 420 }}>
        <div className="region-label" style={{ position: "absolute", top: 12, left: 14, zIndex: 2 }}>
          World News
        </div>
        <Suspense fallback={<div className="region-label" style={{ padding: 16 }}>LOADING GLOBE…</div>}>
          <NewsGlobe items={items} onSelect={openPoint} />
        </Suspense>
      </div>

      <div style={{ borderLeft: "1px solid var(--line)", display: "flex", flexDirection: "column", minHeight: 0 }}>
        <div className="region-label" style={{ padding: "12px 14px 8px" }}>Headlines</div>
        <div style={{ overflowY: "auto", padding: "0 14px 14px", display: "flex", flexDirection: "column", gap: 12 }}>
          {loading && items.length === 0 && (
            <p style={{ color: "var(--text-low)", fontFamily: "var(--font-sans)", fontSize: 13, margin: 0 }}>
              Scanning world media…
            </p>
          )}
          {!loading && items.length === 0 && (
            <p style={{ color: "var(--text-low)", fontFamily: "var(--font-sans)", fontSize: 13, margin: 0, lineHeight: 1.5 }}>
              No world news right now — the GDELT firehose may be rate-limited; it refreshes shortly.
            </p>
          )}
          {items.map((n, i) => (
            <div key={`${n.url ?? n.title}:${i}`} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {n.url ? (
                <a
                  href={n.url}
                  target="_blank"
                  rel="noreferrer noopener"
                  style={{ color: "var(--text-hi)", fontFamily: "var(--font-sans)", fontSize: 13, textDecoration: "none", lineHeight: 1.4 }}
                >
                  {n.title}
                </a>
              ) : (
                <span style={{ color: "var(--text-hi)", fontFamily: "var(--font-sans)", fontSize: 13, lineHeight: 1.4 }}>
                  {n.title}
                </span>
              )}
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                <span className="chip">{n.source}</span>
                {n.country && <span className="chip" style={{ color: "var(--arc-bright)" }}>{n.country}</span>}
                {n.published && <span className="chip">{n.published}</span>}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
