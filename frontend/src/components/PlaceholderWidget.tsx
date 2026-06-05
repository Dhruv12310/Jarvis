// A reserved widget slot for a channel with no source wired yet (Weather, News globe — Wave 2). It
// never invents data; it states the channel is offline. Swap the body for the real widget when the
// endpoint lands (the layout slot + framing are already correct).
import HudPanel from "./HudPanel";

export default function PlaceholderWidget({ label, note }: { label: string; note: string }) {
  return (
    <HudPanel label={label} reticle live={false}>
      <div className="status-pill is-down" style={{ marginBottom: 6 }}>
        <span className="dot" /> offline
      </div>
      <p style={{ color: "var(--text-low)", fontFamily: "var(--font-sans)", fontSize: 12.5, margin: 0, lineHeight: 1.5 }}>
        {note}
      </p>
    </HudPanel>
  );
}
