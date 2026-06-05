// Compact segmented view switcher (COCKPIT | NEWS). On-theme: the active segment is lit arc, the
// rest are quiet. Lives in the StatusBar so it persists across views.
export type View = "cockpit" | "news";

const TABS: { id: View; label: string }[] = [
  { id: "cockpit", label: "Cockpit" },
  { id: "news", label: "News" },
];

export default function NavBar({ view, onChange }: { view: View; onChange: (v: View) => void }) {
  return (
    <div
      role="tablist"
      aria-label="View"
      style={{ display: "inline-flex", gap: 4, padding: 3, border: "1px solid var(--line)", borderRadius: "var(--r-well)", background: "var(--bg-inset)" }}
    >
      {TABS.map((t) => {
        const active = view === t.id;
        return (
          <button
            key={t.id}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(t.id)}
            style={{
              fontFamily: "var(--font-mono)",
              fontWeight: 500,
              fontSize: 10.5,
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              padding: "5px 12px",
              borderRadius: 3,
              cursor: "pointer",
              border: `1px solid ${active ? "rgba(79,216,232,0.4)" : "transparent"}`,
              background: active ? "rgba(79,216,232,0.08)" : "transparent",
              color: active ? "var(--arc-bright)" : "var(--text-low)",
              boxShadow: active ? "inset 0 0 10px -4px var(--arc-glow)" : "none",
              transition: "color 0.15s ease, background 0.15s ease, border-color 0.15s ease",
            }}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}
