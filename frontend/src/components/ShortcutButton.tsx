// A technical control: a crisp rectangular button (hairline border, mono uppercase label, accent
// icon). No pill, no glow bloom — it brightens its border + tints its fill on hover.
import { motion } from "framer-motion";
import type { ReactNode } from "react";

interface Props {
  icon: ReactNode;
  label: string;
  onClick: () => void;
  accent?: "arc" | "gold";
  disabled?: boolean;
}

export default function ShortcutButton({
  icon,
  label,
  onClick,
  accent = "arc",
  disabled = false,
}: Props) {
  const color = accent === "gold" ? "var(--gold)" : "var(--arc)";
  const tint = accent === "gold" ? "rgba(214,162,63,0.08)" : "rgba(90,160,224,0.08)";
  return (
    <motion.button
      onClick={onClick}
      disabled={disabled}
      whileTap={{ scale: 0.98 }}
      whileHover={{ borderColor: color, backgroundColor: tint, color: "var(--text-hi)" }}
      transition={{ duration: 0.14 }}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        padding: "7px 12px",
        borderRadius: 4,
        border: "1px solid var(--line)",
        background: "transparent",
        color: "var(--text-mid)",
        fontFamily: "var(--font-mono)",
        fontWeight: 500,
        fontSize: 11,
        letterSpacing: "0.08em",
        textTransform: "uppercase",
        cursor: disabled ? "default" : "pointer",
        whiteSpace: "nowrap",
        opacity: disabled ? 0.45 : 1,
      }}
    >
      <span style={{ display: "grid", placeItems: "center", color }}>{icon}</span>
      {label}
    </motion.button>
  );
}
