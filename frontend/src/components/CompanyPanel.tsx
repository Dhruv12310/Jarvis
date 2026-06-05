// Company depth modal (mirrors FsModal's pattern). Click a stock tile -> deterministic fundamentals
// (profile, metric grid, analyst trend, recent news) from GET /api/company/{symbol}. A gold "Deep
// Dive" button escalates to the cloud (Anthropic, Tier-2) over the SAME data - gated behind an
// explicit confirm-before-spend strip, labelled CLOUD-ESCALATED, and gracefully disabled w/o a key.
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { CompanyView, DeepDiveResult } from "../types";
import MarkdownBody from "./MarkdownBody";

const pct = (v: number) => `${v.toFixed(1)}%`;
const x1 = (v: number) => v.toFixed(1);
const money = (v: number) => `$${v.toFixed(2)}`;

// Only these metric keys render, with friendly labels — any other key in `metrics` is ignored, so
// the panel never leaks a raw Finnhub field name and never shows a number it can't label.
const METRIC_FIELDS: { key: string; label: string; fmt: (v: number) => string }[] = [
  { key: "pe_ttm", label: "P/E (TTM)", fmt: x1 },
  { key: "ps_ttm", label: "P/S (TTM)", fmt: x1 },
  { key: "pb", label: "P/B", fmt: x1 },
  { key: "gross_margin_ttm", label: "Gross margin", fmt: pct },
  { key: "operating_margin_ttm", label: "Op margin", fmt: pct },
  { key: "net_margin_ttm", label: "Net margin", fmt: pct },
  { key: "roe_ttm", label: "ROE", fmt: pct },
  { key: "revenue_growth_yoy", label: "Rev growth YoY", fmt: pct },
  { key: "revenue_per_share_ttm", label: "Rev / share", fmt: money },
  { key: "eps_ttm", label: "EPS (TTM)", fmt: money },
  { key: "dividend_yield", label: "Div yield", fmt: pct },
  { key: "beta", label: "Beta", fmt: x1 },
];

export default function CompanyPanel({ symbol, onClose }: { symbol: string | null; onClose: () => void }) {
  const reduce = useReducedMotion();
  const [view, setView] = useState<CompanyView | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dive, setDive] = useState<DeepDiveResult | null>(null);
  const [diveLoading, setDiveLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);

  // Fetch on open; cancel-on-reopen guard so a fast re-open on a new symbol can't land stale data.
  useEffect(() => {
    if (!symbol) return;
    let cancelled = false;
    setView(null);
    setError(null);
    setDive(null);
    setConfirming(false);
    setLoading(true);
    api
      .company(symbol)
      .then((v) => !cancelled && setView(v))
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.message : "Could not load company."))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  // Esc closes.
  useEffect(() => {
    if (!symbol) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [symbol, onClose]);

  const runDeepdive = () => {
    if (!symbol) return;
    setConfirming(false);
    setDiveLoading(true);
    api
      .companyDeepdive(symbol)
      .then(setDive)
      .catch((e) =>
        setDive({
          symbol,
          report: null,
          note: e instanceof ApiError ? e.message : "Deep dive failed.",
          escalated: false,
        }),
      )
      .finally(() => setDiveLoading(false));
  };

  const metrics = view?.metrics ?? null;
  const num = (k: string): number | null => (metrics && typeof metrics[k] === "number" ? (metrics[k] as number) : null);
  const present = METRIC_FIELDS.filter((f) => num(f.key) !== null);
  const lo = num("week52_low");
  const hi = num("week52_high");

  return (
    <AnimatePresence>
      {symbol && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: reduce ? 0.12 : 0.18 }}
          onMouseDown={onClose}
          style={{ position: "fixed", inset: 0, zIndex: 60, display: "grid", placeItems: "center", background: "rgba(3,6,10,0.62)", padding: 16 }}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label={`${symbol} company detail`}
            initial={reduce ? { opacity: 0 } : { opacity: 0, scale: 0.96, y: 8 }}
            animate={reduce ? { opacity: 1 } : { opacity: 1, scale: 1, y: 0 }}
            exit={reduce ? { opacity: 0 } : { opacity: 0, scale: 0.97, y: 6 }}
            transition={{ duration: reduce ? 0.12 : 0.2, ease: [0.22, 0.61, 0.36, 1] }}
            onMouseDown={(e) => e.stopPropagation()}
            className="hud-glass hud-reticle hud-glow-active"
            style={{ position: "relative", width: "min(680px, 100%)", maxHeight: "86vh", overflowY: "auto", padding: 20, display: "flex", flexDirection: "column", gap: 14 }}
          >
            <span className="hud-reticle-x" aria-hidden style={{ position: "absolute", inset: 0, pointerEvents: "none" }} />

            <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
              <span style={{ fontFamily: "var(--font-sans)", fontWeight: 600, fontSize: 19, color: "var(--text-hi)" }}>
                {view?.name ?? symbol}
              </span>
              <span className="chip" style={{ color: "var(--arc-bright)" }}>{view?.symbol ?? symbol}</span>
              {view?.industry && <span className="chip">{view.industry}</span>}
              {view?.exchange && <span className="chip">{view.exchange}</span>}
              <button
                onClick={onClose}
                aria-label="Close"
                style={{ marginLeft: "auto", background: "transparent", border: "none", color: "var(--text-low)", cursor: "pointer", fontFamily: "var(--font-mono)", fontSize: 16, lineHeight: 1 }}
              >
                ✕
              </button>
            </div>

            {loading && <div className="region-label">LOADING…</div>}
            {error && <div style={{ fontFamily: "var(--font-mono)", fontSize: 13, color: "var(--danger)" }}>{error}</div>}
            {view?.note && !loading && (
              <p style={{ color: "var(--text-low)", fontFamily: "var(--font-sans)", fontSize: 13, margin: 0 }}>{view.note}</p>
            )}

            {view && !view.note && (
              <>
                <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center" }}>
                  {view.market_cap && (
                    <div className="readout">
                      <span className="readout-label">Market cap</span>
                      <span className="readout-value tabular">{view.market_cap}</span>
                    </div>
                  )}
                  {view.ipo && (
                    <div className="telemetry" style={{ minWidth: 130 }}>
                      <span className="t-label">IPO</span>
                      <span className="t-dots" />
                      <span className="t-value tabular">{view.ipo}</span>
                    </div>
                  )}
                  {view.weburl && (
                    <a href={view.weburl} target="_blank" rel="noreferrer noopener" style={{ color: "var(--arc)", fontFamily: "var(--font-mono)", fontSize: 12 }}>
                      {view.weburl.replace(/^https?:\/\//, "")}
                    </a>
                  )}
                </div>

                {(present.length > 0 || (lo !== null && hi !== null)) && (
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: 8 }}>
                    {present.map((f) => (
                      <div key={f.key} className="readout">
                        <span className="readout-label">{f.label}</span>
                        <span className="readout-value tabular">{f.fmt(num(f.key) as number)}</span>
                      </div>
                    ))}
                    {lo !== null && hi !== null && (
                      <div className="readout">
                        <span className="readout-label">52-wk range</span>
                        <span className="readout-value tabular">
                          ${lo.toFixed(0)}–${hi.toFixed(0)}
                        </span>
                      </div>
                    )}
                  </div>
                )}

                {view.recommendation && (
                  <div>
                    <div className="region-label" style={{ marginBottom: 4 }}>Analyst</div>
                    <p style={{ margin: 0, color: "var(--text-mid)", fontFamily: "var(--font-sans)", fontSize: 13 }}>{view.recommendation}</p>
                  </div>
                )}

                {view.news.length > 0 && (
                  <div>
                    <div className="region-label" style={{ marginBottom: 6 }}>Recent news</div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      {view.news.map((n, i) => (
                        <div key={`${n.url ?? n.title}:${i}`} style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
                          {n.url ? (
                            <a href={n.url} target="_blank" rel="noreferrer noopener" style={{ color: "var(--text-hi)", fontFamily: "var(--font-sans)", fontSize: 13, textDecoration: "none" }}>
                              {n.title}
                            </a>
                          ) : (
                            <span style={{ color: "var(--text-hi)", fontFamily: "var(--font-sans)", fontSize: 13 }}>{n.title}</span>
                          )}
                          <span className="chip" style={{ flexShrink: 0 }}>{n.source}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="hr" />

                <div>
                  {!dive && !confirming && !diveLoading && (
                    <button className="hud-btn" data-accent="gold" onClick={() => setConfirming(true)}>
                      ☁ Deep Dive (cloud)
                    </button>
                  )}
                  {confirming && (
                    <div className="hud-inset" style={{ padding: 12, display: "flex", flexDirection: "column", gap: 10 }}>
                      <span style={{ fontFamily: "var(--font-sans)", fontSize: 13, color: "var(--text-mid)" }}>
                        ☁ This escalates to the cloud (Anthropic) and spends tokens to synthesize an analyst-style report over the data above. Continue?
                      </span>
                      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                        <button className="hud-btn" onClick={() => setConfirming(false)}>Cancel</button>
                        <button className="hud-btn" data-accent="gold" onClick={runDeepdive}>Run Deep Dive</button>
                      </div>
                    </div>
                  )}
                  {diveLoading && <div className="region-label" style={{ marginTop: 8 }}>SYNTHESIZING…</div>}
                  {dive && (
                    <div style={{ marginTop: 10 }}>
                      {dive.report ? (
                        <>
                          <div className="region-label" style={{ color: "var(--gold)", marginBottom: 6 }}>☁ CLOUD-ESCALATED</div>
                          <MarkdownBody source={dive.report} />
                        </>
                      ) : (
                        <p style={{ margin: 0, color: "var(--text-low)", fontFamily: "var(--font-sans)", fontSize: 13 }}>{dive.note}</p>
                      )}
                    </div>
                  )}
                </div>
              </>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
