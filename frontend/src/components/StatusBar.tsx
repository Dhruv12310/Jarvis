// Top instrument cluster: the arc-reactor mark (breathes at idle, spins while thinking, reddens on
// alert), the JARVIS wordmark, a telemetry-lite readout (uptime + link), the SystemPill health
// cluster, and the live Clock. The mark is the global activity indicator. Corner-reticle framed.
import type { ReactNode } from "react";
import type { SystemHealth } from "../types";
import ArcReactorLogo from "./ArcReactorLogo";
import Clock from "./Clock";
import SystemPill from "./SystemPill";
import Telemetry from "./Telemetry";

interface Props {
  systems: SystemHealth[];
  busy?: boolean;
  alert?: boolean;
  uptime?: string; // "HH:MM:SS" since the cockpit powered on
  nav?: ReactNode; // the view switcher (Cockpit | News), persistent across views
}

export default function StatusBar({ systems, busy = false, alert = false, uptime, nav }: Props) {
  const reactorState = alert ? "alert" : busy ? "thinking" : "idle";
  return (
    <div
      className="hud-glass hud-reticle"
      style={{ height: "100%", display: "flex", alignItems: "center", gap: 14, padding: "0 16px", position: "relative" }}
    >
      <span className="hud-reticle-x" aria-hidden />
      <ArcReactorLogo size={28} state={reactorState} />
      <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600, fontSize: 17, letterSpacing: "0.3em", color: "var(--text-hi)" }}>
        JARVIS
      </span>
      <span className="region-label" style={{ borderLeft: "1px solid var(--line)", paddingLeft: 12 }}>
        Local Assistant
      </span>

      {nav && <div style={{ marginLeft: 6 }}>{nav}</div>}

      <div style={{ flex: 1 }} />

      <div className="statusbar-telemetry" style={{ display: "flex", flexDirection: "column", gap: 1, minWidth: 150, marginRight: 6 }}>
        <Telemetry label="UPTIME" value={uptime ?? "00:00:00"} />
        <Telemetry label="LINK" value={alert ? "DOWN" : "ONLINE"} trend={alert ? "down" : "up"} />
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        {systems.map((s) => (
          <SystemPill key={s.id} label={s.label} state={s.state} />
        ))}
      </div>
      <div style={{ width: 1, height: 22, background: "var(--line)" }} />
      <Clock />
    </div>
  );
}
