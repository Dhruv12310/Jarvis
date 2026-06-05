// A glowing status dot + Rajdhani uppercase label; slow pulse on 'ok'.
import { motion, useReducedMotion } from "framer-motion";
import type { SystemState } from "../types";

const COLOR: Record<SystemState, string> = {
  ok: "var(--ok)",
  warn: "var(--gold)",
  down: "var(--danger)",
};

export default function SystemPill({ label, state }: { label: string; state: SystemState }) {
  const reduce = useReducedMotion();
  const color = COLOR[state];
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          fontWeight: 500,
          letterSpacing: "0.14em",
          textTransform: "uppercase",
          color: "var(--text-low)",
        }}
      >
        {label}
      </span>
      <motion.span
        animate={state === "ok" && !reduce ? { opacity: [0.5, 1, 0.5] } : { opacity: 1 }}
        transition={
          state === "ok" && !reduce
            ? { duration: 3.2, repeat: Infinity, ease: "easeInOut" }
            : undefined
        }
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: color,
          boxShadow: `0 0 6px ${color}`,
        }}
      />
    </span>
  );
}
