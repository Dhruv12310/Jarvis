// Per-kind thin-line glyph, tinted to the kind's accent. Simple inline SVGs (no icon dep).
import type { CardKind } from "../types";

const RAIL: Record<CardKind, string> = {
  briefing: "var(--arc)",
  answer: "var(--arc)",
  chat: "var(--text-mid)",
  agenda: "var(--arc)",
  goal: "var(--gold)",
  finance: "var(--ok)",
  suggestion: "var(--gold)",
  error: "var(--danger)",
};

export function railColor(kind: CardKind): string {
  return RAIL[kind];
}

const PATHS: Record<CardKind, JSX.Element> = {
  briefing: (
    <>
      <path d="M4 5h16M4 10h16M4 15h10" />
    </>
  ),
  answer: <path d="M21 11.5a8.5 8.5 0 1 1-3.4-6.8L21 4l-1 4-4-1 1.6-1.2" />,
  chat: <path d="M4 5h16v10H9l-5 4V5z" />,
  agenda: (
    <>
      <rect x="4" y="5" width="16" height="15" rx="2" />
      <path d="M4 9h16M8 3v4M16 3v4" />
    </>
  ),
  goal: (
    <>
      <circle cx="12" cy="12" r="8" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
  finance: <path d="M4 16l5-5 4 3 7-8" />,
  suggestion: <path d="M12 3a6 6 0 0 0-4 10.5V16h8v-2.5A6 6 0 0 0 12 3zM9 19h6M10 21h4" />,
  error: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v6M12 16.5v.5" />
    </>
  ),
};

export default function KindIcon({ kind, size = 16 }: { kind: CardKind; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={RAIL[kind]}
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      {PATHS[kind]}
    </svg>
  );
}
