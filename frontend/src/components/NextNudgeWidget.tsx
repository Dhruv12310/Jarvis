// The standing "next nudge": the top PUSH suggestion's first line. Gold = owned/act-on. Clicking
// expands it into the feed (runs controller.showSuggestions via App's onOpen). Distinct from the
// richer Goal Feed (pull): this is the strict push engine's single highest-value nudge.
import HudPanel from "./HudPanel";

interface Props {
  top?: { content: string; why: string };
  onOpen: () => void;
}

export default function NextNudgeWidget({ top, onOpen }: Props) {
  return (
    <HudPanel label="Next Nudge" reticle live={!!top} liveColor="var(--gold)" glow={top ? "gold" : "none"}>
      <button
        onClick={onOpen}
        style={{
          display: "flex",
          gap: 10,
          alignItems: "flex-start",
          textAlign: "left",
          background: "transparent",
          border: "none",
          cursor: "pointer",
          padding: 0,
          width: "100%",
        }}
      >
        <span
          style={{
            color: top ? "var(--text-mid)" : "var(--text-low)",
            fontFamily: "var(--font-sans)",
            fontSize: 13,
            lineHeight: 1.5,
          }}
        >
          {top ? top.content : "Tap to check for suggestions →"}
        </span>
      </button>
    </HudPanel>
  );
}
