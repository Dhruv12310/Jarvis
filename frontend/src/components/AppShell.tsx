// Top-level cockpit layout. CSS grid: full-width status, an optional full-width ticker strip, the
// feed | side rail, and a full-width dock. Regions power on top -> bottom (~0.6s, no fake boot log).
// Below 1180px the denser rail becomes a slide-over drawer so the feed keeps the full width.
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { type ReactNode, useEffect, useState } from "react";
import { DUR, EASE } from "../motion";

function useMediaQuery(query: string): boolean {
  const [match, setMatch] = useState(() =>
    typeof window !== "undefined" ? window.matchMedia(query).matches : true,
  );
  useEffect(() => {
    const mq = window.matchMedia(query);
    const on = () => setMatch(mq.matches);
    on();
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [query]);
  return match;
}

interface Props {
  statusBar: ReactNode;
  ticker?: ReactNode;
  feed: ReactNode;
  side: ReactNode;
  dock: ReactNode;
  hideSide?: boolean; // News view hides the rail so the center (globe) gets full width
}

const regionAnim = (delay: number, reduce: boolean | null) =>
  reduce
    ? { initial: { opacity: 0 }, animate: { opacity: 1, transition: { duration: DUR.fast } } }
    : {
        initial: { opacity: 0, y: 10 },
        animate: { opacity: 1, y: 0, transition: { duration: DUR.slow, ease: EASE, delay } },
      };

export default function AppShell({ statusBar, ticker, feed, side, dock, hideSide = false }: Props) {
  const reduce = useReducedMotion();
  const wide = useMediaQuery("(min-width: 1180px)");
  const [drawer, setDrawer] = useState(false);
  const showSide = wide && !hideSide;

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: showSide ? "1fr 360px" : "1fr",
        gridTemplateRows: "56px auto minmax(0, 1fr) auto", // status | ticker | feed/side | dock
        gridTemplateAreas: showSide
          ? '"status status" "ticker ticker" "feed side" "dock dock"'
          : '"status" "ticker" "feed" "dock"',
        height: "100vh",
        maxWidth: 1640,
        margin: "0 auto",
        gap: 14,
        padding: 14,
        overflow: "hidden",
      }}
    >
      <motion.div style={{ gridArea: "status", minWidth: 0 }} {...regionAnim(0, reduce)}>
        {statusBar}
      </motion.div>

      {ticker && (
        <div style={{ gridArea: "ticker", minWidth: 0 }}>{ticker}</div>
      )}

      <motion.div style={{ gridArea: "feed", minHeight: 0, minWidth: 0 }} {...regionAnim(0.2, reduce)}>
        {feed}
      </motion.div>

      {showSide && (
        <motion.div style={{ gridArea: "side", minHeight: 0 }} {...regionAnim(0.1, reduce)}>
          {side}
        </motion.div>
      )}

      <motion.div style={{ gridArea: "dock", minWidth: 0 }} {...regionAnim(0.15, reduce)}>
        {dock}
      </motion.div>

      {/* narrow (and rail not hidden): floating toggle + slide-over drawer for the side rail */}
      {!wide && !hideSide && (
        <>
          <button
            onClick={() => setDrawer(true)}
            aria-label="Open panels"
            className="hud-btn"
            style={{ position: "fixed", right: 18, top: 70, zIndex: 30, padding: "8px 12px" }}
          >
            Panels
          </button>
          <AnimatePresence>
            {drawer && (
              <>
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  onClick={() => setDrawer(false)}
                  style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", zIndex: 40 }}
                />
                <motion.div
                  initial={{ x: 380 }}
                  animate={{ x: 0 }}
                  exit={{ x: 380 }}
                  transition={{ duration: DUR.base, ease: EASE }}
                  style={{
                    position: "fixed",
                    top: 0,
                    right: 0,
                    bottom: 0,
                    width: 380,
                    maxWidth: "88vw",
                    zIndex: 50,
                    padding: 16,
                    background: "var(--bg-raised)",
                    overflowY: "auto",
                  }}
                >
                  {side}
                </motion.div>
              </>
            )}
          </AnimatePresence>
        </>
      )}
    </div>
  );
}
