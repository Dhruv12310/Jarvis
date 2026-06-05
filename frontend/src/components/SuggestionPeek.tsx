// Always-visible "next nudge" preview at the bottom of the side rail. Shows the top suggestion's
// first line + a gold dot; clicking opens it into the feed (runs show_suggestions).
import HudPanel from "./HudPanel";

interface Props {
  top?: { content: string; why: string };
  onOpen: () => void;
}

export default function SuggestionPeek({ top, onOpen }: Props) {
  return (
    <HudPanel label="Next nudge">
      {top ? (
        <button
          onClick={onOpen}
          style={{
            display: "flex",
            gap: 10,
            alignItems: "flex-start",
            background: "transparent",
            border: "none",
            textAlign: "left",
            cursor: "pointer",
            padding: 0,
            width: "100%",
          }}
        >
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: "var(--gold)",
              boxShadow: "0 0 6px var(--gold)",
              marginTop: 6,
              flexShrink: 0,
            }}
          />
          <span style={{ fontFamily: "var(--font-sans)", fontSize: 13, color: "var(--text-mid)", lineHeight: 1.5 }}>
            {top.content}
          </span>
        </button>
      ) : (
        <button
          onClick={onOpen}
          style={{
            background: "transparent",
            border: "none",
            color: "var(--text-low)",
            fontFamily: "var(--font-sans)",
            fontSize: 13,
            cursor: "pointer",
            padding: 0,
          }}
        >
          Tap to check for suggestions →
        </button>
      )}
    </HudPanel>
  );
}
