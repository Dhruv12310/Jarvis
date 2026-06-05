// FsModal — a small "engineered instrument" dialog for the +File / +Folder shortcuts. Corner
// reticles + a mono path well, NOT a bubbly system dialog. Enter submits (path field); in file mode
// Cmd/Ctrl+Enter submits from the content textarea (plain Enter = newline). Esc / backdrop closes.
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { type CSSProperties, useEffect, useRef, useState } from "react";

export type FsMode = "file" | "folder";

interface Props {
  mode: FsMode | null; // null = closed (drives AnimatePresence)
  busy?: boolean;
  onSubmit: (path: string, content: string) => void;
  onClose: () => void;
}

export default function FsModal({ mode, busy = false, onSubmit, onClose }: Props) {
  const reduce = useReducedMotion();
  const [path, setPath] = useState("");
  const [content, setContent] = useState("");
  const pathRef = useRef<HTMLInputElement>(null);

  // Reset + focus whenever the modal (re)opens.
  useEffect(() => {
    if (mode) {
      setPath("");
      setContent("");
      const t = setTimeout(() => pathRef.current?.focus(), 0);
      return () => clearTimeout(t);
    }
  }, [mode]);

  // Esc closes from anywhere while open.
  useEffect(() => {
    if (!mode) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mode, onClose]);

  const submit = () => {
    if (busy || !path.trim()) return;
    onSubmit(path, content);
  };

  const isFile = mode === "file";
  const title = isFile ? "Create file" : "Create folder";
  const accent = isFile ? "var(--arc)" : "var(--gold)";
  const glowClass = isFile ? "hud-glow-active" : "hud-glow-gold";

  const fieldStyle: CSSProperties = {
    width: "100%",
    padding: "10px 12px",
    background: "var(--bg-inset)",
    border: "1px solid var(--line)",
    borderRadius: "var(--r-well)",
    outline: "none",
    color: "var(--text-hi)",
    fontFamily: "var(--font-mono)",
    fontSize: 13,
    letterSpacing: "0.02em",
  };

  return (
    <AnimatePresence>
      {mode && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: reduce ? 0.12 : 0.18 }}
          onMouseDown={onClose}
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 60,
            display: "grid",
            placeItems: "center",
            background: "rgba(3, 6, 10, 0.62)",
            padding: 16,
          }}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label={title}
            initial={reduce ? { opacity: 0 } : { opacity: 0, scale: 0.96, y: 8 }}
            animate={reduce ? { opacity: 1 } : { opacity: 1, scale: 1, y: 0 }}
            exit={reduce ? { opacity: 0 } : { opacity: 0, scale: 0.97, y: 6 }}
            transition={{ duration: reduce ? 0.12 : 0.2, ease: [0.22, 0.61, 0.36, 1] }}
            onMouseDown={(e) => e.stopPropagation()}
            className={`hud-glass hud-reticle ${glowClass}`}
            style={{ position: "relative", width: "min(520px, 100%)", padding: 18, display: "flex", flexDirection: "column", gap: 14 }}
          >
            <span className="hud-reticle-x" aria-hidden style={{ position: "absolute", inset: 0, pointerEvents: "none" }} />

            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span className="hud-hex" style={{ "--hex": accent } as CSSProperties} aria-hidden />
              <span className="region-label">{title}</span>
            </div>

            <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <span className="region-label" style={{ fontSize: 9.5, opacity: 0.8 }}>
                Absolute path
              </span>
              <input
                ref={pathRef}
                value={path}
                onChange={(e) => setPath(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    submit();
                  }
                }}
                spellCheck={false}
                autoComplete="off"
                placeholder={isFile ? "C:\\Users\\you\\notes\\todo.txt" : "C:\\Users\\you\\projects\\new"}
                style={fieldStyle}
              />
            </label>

            {isFile && (
              <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <span className="region-label" style={{ fontSize: 9.5, opacity: 0.8 }}>
                  Content (optional)
                </span>
                <textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                      e.preventDefault();
                      submit();
                    }
                  }}
                  rows={5}
                  spellCheck={false}
                  placeholder="(empty file)"
                  style={{ ...fieldStyle, resize: "vertical", minHeight: 96, fontSize: 12.5, lineHeight: 1.5 }}
                />
              </label>
            )}

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 2 }}>
              <button type="button" className="hud-btn" onClick={onClose} disabled={busy}>
                Cancel
              </button>
              <button
                type="button"
                className="hud-btn"
                data-accent={isFile ? undefined : "gold"}
                onClick={submit}
                disabled={busy || !path.trim()}
              >
                {busy ? "Working…" : title}
              </button>
            </div>

            <div className="region-label" style={{ fontSize: 9, opacity: 0.55, textAlign: "right" }}>
              {isFile ? "⌘/Ctrl+Enter" : "Enter"} to create · Esc to close
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
