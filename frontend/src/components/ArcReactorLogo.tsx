// The system mark + global activity indicator — a precise instrument gauge, not a glowing dot:
// a thin outer ring, a fine tick ring, crosshair ticks, and a small core. idle = still; thinking =
// the tick ring rotates slowly; alert = the mark turns red.
import { motion, useReducedMotion } from "framer-motion";

interface Props {
  size?: number;
  state?: "idle" | "thinking" | "alert";
}

const TICKS = 24;

export default function ArcReactorLogo({ size = 26, state = "idle" }: Props) {
  const reduce = useReducedMotion();
  const c = size / 2;
  const color = state === "alert" ? "var(--danger)" : "var(--arc)";
  const tickR = size * 0.42;
  const ringR = size * 0.3;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden>
      {/* outer ring */}
      <circle cx={c} cy={c} r={size * 0.46} fill="none" stroke="var(--line-strong)" strokeWidth={1} />
      {/* fine tick ring (rotates while thinking) */}
      <motion.g
        animate={state === "thinking" && !reduce ? { rotate: 360 } : { rotate: 0 }}
        transition={
          state === "thinking" && !reduce
            ? { duration: 8, repeat: Infinity, ease: "linear" }
            : { duration: 0.4 }
        }
        style={{ transformOrigin: "center" }}
      >
        {Array.from({ length: TICKS }).map((_, i) => {
          const a = (i / TICKS) * Math.PI * 2;
          const major = i % 6 === 0;
          const inner = tickR - (major ? 3 : 1.5);
          return (
            <line
              key={i}
              x1={c + Math.cos(a) * inner}
              y1={c + Math.sin(a) * inner}
              x2={c + Math.cos(a) * tickR}
              y2={c + Math.sin(a) * tickR}
              stroke={major ? color : "var(--line-strong)"}
              strokeWidth={1}
              opacity={major ? 0.85 : 0.5}
            />
          );
        })}
      </motion.g>
      {/* inner ring + core */}
      <circle cx={c} cy={c} r={ringR} fill="none" stroke={color} strokeWidth={1} opacity={0.7} />
      <motion.circle
        cx={c}
        cy={c}
        r={size * 0.12}
        fill={color}
        animate={reduce ? undefined : { opacity: state === "alert" ? [1, 0.5, 1] : [0.7, 1, 0.7] }}
        transition={
          reduce ? undefined : { duration: state === "alert" ? 1 : 3.4, repeat: Infinity, ease: "easeInOut" }
        }
      />
    </svg>
  );
}
