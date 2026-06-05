// The ask() surface. Frosted inset field (Inter 15) + arc-ring send button. Enter submits,
// Shift+Enter newlines, empty input is a no-op (mirrors the controller early-return). While busy,
// the send ring goes indeterminate. Value is lifted to App so the +Goal shortcut can reuse it.
import { useReducedMotion } from "framer-motion";
import { useRef } from "react";
import ArcRing from "./ArcRing";

interface Props {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  busy?: boolean;
  placeholder?: string;
}

export default function ChatInput({
  value,
  onChange,
  onSubmit,
  busy = false,
  placeholder = "Ask Jarvis…",
}: Props) {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLTextAreaElement>(null);

  const submit = () => {
    if (busy || !value.trim()) return;
    onSubmit();
  };

  return (
    <div
      className="hud-inset"
      style={{ display: "flex", alignItems: "flex-end", gap: 10, padding: 8 }}
    >
      <textarea
        ref={ref}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
        rows={1}
        placeholder={placeholder}
        style={{
          flex: 1,
          resize: "none",
          background: "transparent",
          border: "none",
          outline: "none",
          color: "var(--text-hi)",
          fontFamily: "var(--font-sans)",
          fontSize: 15,
          lineHeight: 1.5,
          padding: "8px 8px",
          maxHeight: 140,
        }}
      />
      <button
        onClick={submit}
        disabled={busy || !value.trim()}
        aria-label="Send"
        style={{
          background: "transparent",
          border: "none",
          cursor: busy || !value.trim() ? "default" : "pointer",
          padding: 2,
          position: "relative",
          display: "grid",
          placeItems: "center",
          opacity: !value.trim() && !busy ? 0.5 : 1,
          transition: reduce ? undefined : "opacity .18s ease",
        }}
      >
        <ArcRing
          size={36}
          value={value.trim() ? 1 : 0.001}
          indeterminate={busy}
          strokeWidth={2.5}
        />
        <span style={{ position: "absolute", color: "var(--arc-bright)", fontSize: 14 }} aria-hidden>
          ➤
        </span>
      </button>
    </div>
  );
}
