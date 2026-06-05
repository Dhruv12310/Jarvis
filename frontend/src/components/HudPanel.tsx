// The universal instrument-panel container every region/panel/card composes. Solid face + hairline
// at rest; glow only on focus/active/owned (glow always MEANS something). Optional corner-reticle
// frame + a live "●" channel dot (lit + breathing only when the channel is genuinely live) give the
// cockpit its eDEX framing — all back-compatible (defaults reproduce the original render exactly).
import { motion, useReducedMotion } from "framer-motion";
import type { ReactNode } from "react";
import { pillPulse } from "../motion";

type Glow = "none" | "arc" | "gold" | "danger";

interface Props {
  glow?: Glow;
  label?: string;
  reticle?: boolean; // opt into corner-reticle framing
  live?: boolean; // show + pulse a "●" channel dot beside the label
  liveColor?: string; // defaults --ok; pass --gold for owned channels
  action?: ReactNode; // a small right-aligned control (count chip / refresh)
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
}

const GLOW_CLASS: Record<Glow, string> = {
  none: "",
  arc: "hud-glow-active",
  gold: "hud-glow-gold",
  danger: "hud-glow-danger",
};

export default function HudPanel({
  glow = "none",
  label,
  reticle = false,
  live = false,
  liveColor = "var(--ok)",
  action,
  className = "",
  bodyClassName = "",
  children,
}: Props) {
  const reduce = useReducedMotion();
  return (
    <section
      className={`hud-glass ${reticle ? "hud-reticle" : ""} ${GLOW_CLASS[glow]} ${className}`}
      style={reticle ? { position: "relative" } : undefined}
    >
      {reticle && <span className="hud-reticle-x" aria-hidden />}
      {label && (
        <>
          <header style={{ padding: "12px 16px 0", display: "flex", alignItems: "center", gap: 8 }}>
            {live && (
              <motion.span
                aria-hidden
                {...pillPulse(!!reduce, live)}
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  background: liveColor,
                  color: liveColor,
                  flexShrink: 0,
                }}
              />
            )}
            <span className="region-label">{label}</span>
            {action && <div style={{ marginLeft: "auto" }}>{action}</div>}
          </header>
          <div className="hr" style={{ margin: "8px 16px 0" }} />
        </>
      )}
      <div className={bodyClassName} style={{ padding: label ? "10px 16px 14px" : 14 }}>
        {children}
      </div>
    </section>
  );
}
