// The append-only feed: maps the card list -> Card components, staggered blur-in via AnimatePresence
// + layout, auto-scrolling to the newest card at the BOTTOM (mirrors the Flet ListView auto_scroll).
// Inner content capped at 720px so prose never exceeds a comfortable measure on a wide monitor.
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useRef } from "react";
import { cardIn } from "../motion";
import type { CardData } from "../types";
import Card from "./Card";

export interface FeedItem extends CardData {
  id: number;
  time: string;
}

export default function Feed({ cards }: { cards: FeedItem[] }) {
  const reduce = useReducedMotion();
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "end" });
  }, [cards.length, reduce]);

  return (
    <div style={{ height: "100%", overflowY: "auto" }}>
      <div className="feed-inner" style={{ maxWidth: 760, margin: "0 auto", padding: "2px 4px 8px" }}>
        <span className="region-label" style={{ display: "block", margin: "2px 2px 12px" }}>
          Feed
        </span>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <AnimatePresence initial={false}>
            {cards.map((card, index) => (
              <motion.div
                key={card.id}
                layout={!reduce}
                variants={cardIn(index)}
                initial="initial"
                animate="animate"
                exit="exit"
              >
                <Card card={card} time={card.time} />
              </motion.div>
            ))}
          </AnimatePresence>
          <div ref={endRef} />
        </div>
      </div>
    </div>
  );
}
