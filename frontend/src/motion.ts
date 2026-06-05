// Centralized animation language (HYBRID HUD). Cinematic on arrival and at the edges, calm at
// rest. Every loop is opacity/transform/filter only (GPU-cheap). Looping helpers take the
// useReducedMotion() result `rm` and collapse to a still frame at the SOURCE, so the reading
// column and reduced-motion users never see a loop. Nothing animates under prose.
import type { Variants, Transition } from "framer-motion";

export const EASE = [0.22, 0.61, 0.36, 1] as const;
export const DUR = { fast: 0.22, base: 0.34, slow: 0.55 } as const;

// ── Shell regions power on top -> bottom (~0.6s, no fake boot log). ─────────────────────────
export const region: Variants = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0, transition: { duration: DUR.slow, ease: EASE } },
};

// ── The signature feed motion: blur-in, newest at the bottom. ───────────────────────────────
export const cardIn = (index: number): Variants => ({
  initial: { opacity: 0, y: 14, filter: "blur(4px)" },
  animate: {
    opacity: 1,
    y: 0,
    filter: "blur(0px)",
    transition: { duration: DUR.base, ease: EASE, delay: Math.min(index * 0.05, 0.3) },
  },
  exit: { opacity: 0, y: -8, transition: { duration: DUR.fast, ease: EASE } },
});

// rm-collapsing variant of cardIn for one-call ergonomics (fade only when reduced).
export const cardInRM = (index: number, rm: boolean): Variants =>
  rm
    ? {
        initial: { opacity: 0 },
        animate: { opacity: 1, transition: { duration: DUR.fast, ease: EASE } },
        exit: { opacity: 0, transition: { duration: DUR.fast, ease: EASE } },
      }
    : cardIn(index);

// ── One-shot rail glow-flare on first paint — confined to the 2px spine, never under text. ──
export const railFlare = {
  boxShadow: ["0 0 0px var(--rail)", "0 0 14px -1px var(--rail)", "0 0 8px -1px var(--rail)"],
};
export const railFlareTransition = { duration: 0.7, ease: EASE } as const;

export const hoverLift = {
  whileHover: { y: -2, transition: { duration: DUR.fast, ease: EASE } },
  whileTap: { scale: 0.97 },
};

// ── Idle "alive" cue for status pills + the reactor core. ───────────────────────────────────
export const statusPulse = {
  animate: { opacity: [0.55, 1, 0.55] },
  transition: { duration: 3.2, repeat: Infinity, ease: "easeInOut" as const },
};

// ── Dignified thinking spin (not a spinner race). ───────────────────────────────────────────
export const arcThinking = {
  animate: { rotate: 360 },
  transition: { duration: 6, repeat: Infinity, ease: "linear" as const },
};

// ═══════════════════════ HYBRID HUD cinematic widget additions ═══════════════════════════════
// Discipline: pass rm = useReducedMotion() at the call site. When rm is true, each returns a
// still frame. Pair every infinite loop here with a real STATE (live/active/owned), never decor.

// 1. ARC-REACTOR idle breathe — the core's drop-shadow swells; the mark barely scales. "Alive."
export const reactorBreathe = (rm: boolean) =>
  rm
    ? { animate: { opacity: 1 } }
    : {
        animate: {
          scale: [1, 1.025, 1],
          filter: [
            "drop-shadow(0 0 5px var(--arc-glow))",
            "drop-shadow(0 0 11px var(--arc-glow))",
            "drop-shadow(0 0 5px var(--arc-glow))",
          ],
        },
        transition: { duration: 3.4, repeat: Infinity, ease: "easeInOut" as const },
      };

// 2. ARC-REACTOR thinking spin — housing + value ring counter-rotate for depth.
export const reactorThinking = (rm: boolean) =>
  rm
    ? { animate: { rotate: 0 } }
    : { animate: { rotate: 360 }, transition: { duration: 6, repeat: Infinity, ease: "linear" as const } };
export const reactorThinkingInner = (rm: boolean) =>
  rm
    ? { animate: { rotate: 0 } }
    : { animate: { rotate: -360 }, transition: { duration: 9, repeat: Infinity, ease: "linear" as const } };

// 3. FRAME SCAN-SWEEP — ONE faint cyan line sweeps a HERO panel top->bottom ONCE on mount, then
//    rests. The "powering on" beat at the edge — NOT a looping scanline (that's slop).
//    Render a 1px gradient bar absolutely positioned; this animates its `top`.
export const frameScan = (rm: boolean) =>
  rm
    ? { initial: { opacity: 0 }, animate: { opacity: 0 } }
    : {
        initial: { top: "0%", opacity: 0 },
        animate: { top: ["0%", "100%"], opacity: [0, 0.6, 0], transition: { duration: 0.9, ease: EASE } },
      };
// pair with: <div style={{position:'absolute',left:0,right:0,height:1,
//   background:'linear-gradient(90deg,transparent,var(--arc),transparent)'}} />

// 4. TICKER SCROLL — drives .hud-ticker-track in JS (alt to the CSS keyframe). Duplicate the
//    item set in markup; translate by exactly -50% so the loop is seamless.
export const tickerScroll = (rm: boolean, durationSec = 38): { animate: { x: string[] }; transition: Transition } =>
  rm
    ? { animate: { x: ["0%", "0%"] }, transition: { duration: 0 } }
    : { animate: { x: ["0%", "-50%"] }, transition: { duration: durationSec, repeat: Infinity, ease: "linear" } };

// 5. SCANLINE DRIFT — a single faint band sweeping an edge widget. Texture, not a strobe.
//    heightPx = the widget height. Reduced motion: omit entirely (render no band).
export const scanDrift = (rm: boolean, heightPx = 200, durationSec = 7.5) =>
  rm
    ? null
    : {
        initial: { y: -heightPx * 0.3, opacity: 0 },
        animate: { y: [-heightPx * 0.3, heightPx * 1.05], opacity: [0, 0.5, 0.5, 0] },
        transition: { duration: durationSec, repeat: Infinity, ease: "linear" as const, times: [0, 0.1, 0.9, 1] },
      };

// 6. SPARKLINE DRAW-ON — line draws L->R via pathLength, once, on mount/data-refresh.
export const sparkDraw = (rm: boolean, delaySec = 0): Variants =>
  rm
    ? { initial: { pathLength: 1, opacity: 1 }, animate: { pathLength: 1, opacity: 1 } }
    : {
        initial: { pathLength: 0, opacity: 0.4 },
        animate: {
          pathLength: 1,
          opacity: 1,
          transition: { pathLength: { duration: 0.9, ease: EASE, delay: delaySec }, opacity: { duration: 0.2, delay: delaySec } },
        },
      };

// 7. READOUT TICK — one-shot flash when a live stat changes (no loop). "It updated."
export const readoutTick = (rm: boolean) =>
  rm
    ? {}
    : { animate: { color: ["var(--arc-bright)", "var(--text-hi)"] }, transition: { duration: 0.5, ease: EASE } };

// 8. BAR-GAUGE FILL — system-monitor bars animate to value on mount/update. <i> needs
//    transform-origin: left (set in CSS). pct is 0..100.
export const barFill = (rm: boolean, pct: number): Variants => ({
  initial: { scaleX: 0 },
  animate: {
    scaleX: Math.max(0, Math.min(1, pct / 100)),
    transition: { duration: rm ? 0 : DUR.base, ease: EASE },
  },
});

// 9. STATUS-PILL / HEX dot pulse — a live channel "breathes" its halo. Drive on the .dot, only
//    when the channel is genuinely live/active. Tighter+dimmer than statusPulse so a wall of
//    pills doesn't strobe.
export const pillPulse = (rm: boolean, live: boolean) =>
  rm || !live
    ? { animate: { boxShadow: "0 0 6px -1px currentColor" } }
    : {
        animate: { boxShadow: ["0 0 4px -1px currentColor", "0 0 9px 0px currentColor", "0 0 4px -1px currentColor"] },
        transition: { duration: 2.6, repeat: Infinity, ease: "easeInOut" as const },
      };

// 10. HEX NODE PULSE — slow opacity pulse for active map endpoints / collector nodes. Loops only
//     when the node is active (the eDEX "live link" cue).
export const hexPulse = (rm: boolean, active: boolean) =>
  rm || !active
    ? { animate: { opacity: active ? 1 : 0.5 } }
    : { animate: { opacity: [0.5, 1, 0.5] }, transition: { duration: 2.6, repeat: Infinity, ease: "easeInOut" as const } };
