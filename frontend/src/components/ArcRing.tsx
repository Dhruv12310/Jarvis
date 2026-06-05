// Reusable SVG arc gauge / decoration. The circular motif only ever where it holds ONE value or
// is a control edge - never around a card or under text (spec §7).
import { motion, useReducedMotion } from "framer-motion";

interface Props {
  value?: number; // 0..1 (omit for a decorative full track)
  size?: number;
  accent?: "arc" | "gold";
  indeterminate?: boolean;
  showLabel?: boolean;
  strokeWidth?: number;
}

export default function ArcRing({
  value = 0,
  size = 44,
  accent = "arc",
  indeterminate = false,
  showLabel = false,
  strokeWidth = 2.5,
}: Props) {
  const reduce = useReducedMotion();
  const r = (size - strokeWidth) / 2;
  const c = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(1, value));
  const dash = indeterminate ? c * 0.25 : c * clamped;
  const stroke = accent === "gold" ? "var(--gold)" : "var(--arc)";
  const glow = accent === "gold" ? "rgba(245,196,81,0.4)" : "var(--arc-glow)";

  return (
    <div style={{ position: "relative", width: size, height: size }}>
      <motion.svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        animate={indeterminate && !reduce ? { rotate: 360 } : undefined}
        transition={
          indeterminate && !reduce
            ? { duration: 1.1, repeat: Infinity, ease: "linear" }
            : undefined
        }
        style={{ transform: "rotate(-90deg)" }}
      >
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--arc-faint)"
          strokeWidth={strokeWidth}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={stroke}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={`${dash} ${c}`}
          style={{ filter: `drop-shadow(0 0 4px ${glow})`, transition: "stroke-dasharray .5s ease" }}
        />
      </motion.svg>
      {showLabel && (
        <span
          className="tabular"
          style={{
            position: "absolute",
            inset: 0,
            display: "grid",
            placeItems: "center",
            fontFamily: "var(--font-mono)",
            fontSize: size * 0.26,
            color: "var(--text-mid)",
          }}
        >
          {Math.round(clamped * 100)}
        </span>
      )}
    </div>
  );
}
