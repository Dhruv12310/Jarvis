// Owned-data panel: each goal as a gold progress ring + mono #id + Inter description, with an
// inline add field. Gold-leaning because goals are user-owned.
import { useState } from "react";
import type { Goal } from "../types";
import ArcRing from "./ArcRing";
import HudPanel from "./HudPanel";

interface Props {
  goals: Goal[];
  onAdd: (text: string) => void;
}

export default function GoalsPanel({ goals, onAdd }: Props) {
  const [text, setText] = useState("");
  const active = goals.filter((g) => g.status !== "done");

  const submit = () => {
    if (!text.trim()) return;
    onAdd(text.trim());
    setText("");
  };

  return (
    <HudPanel label="Goals" glow="gold">
      {active.length === 0 ? (
        <p style={{ color: "var(--text-low)", fontFamily: "var(--font-sans)", fontSize: 14, margin: 0 }}>
          No goals yet.
        </p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {active.map((g) => (
            <div key={g.id} style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <ArcRing value={g.progress ?? 0} size={30} accent="gold" strokeWidth={2.5} />
              <span
                className="tabular"
                style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--gold)", flexShrink: 0 }}
              >
                #{g.id}
              </span>
              <span style={{ fontFamily: "var(--font-sans)", fontSize: 14, color: "var(--text-hi)" }}>
                {g.description}
              </span>
            </div>
          ))}
        </div>
      )}
      <div className="hud-inset" style={{ marginTop: 12, display: "flex", padding: 4 }}>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder="Add a goal…"
          style={{
            flex: 1,
            background: "transparent",
            border: "none",
            outline: "none",
            color: "var(--text-hi)",
            fontFamily: "var(--font-sans)",
            fontSize: 13,
            padding: "6px 8px",
          }}
        />
        <button
          onClick={submit}
          aria-label="Add goal"
          style={{
            background: "transparent",
            border: "none",
            color: "var(--gold)",
            cursor: "pointer",
            fontSize: 18,
            padding: "0 8px",
          }}
        >
          +
        </button>
      </div>
    </HudPanel>
  );
}
