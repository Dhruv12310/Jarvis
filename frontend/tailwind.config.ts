import type { Config } from "tailwindcss";

// Identity lives in two files: theme.css (the CSS variables + effect recipes) and motion.ts.
// Tailwind maps a few semantic tokens onto those variables so utility classes stay on-palette.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        void: "var(--bg-void)",
        base: "var(--bg-base)",
        raised: "var(--bg-raised)",
        arc: "var(--arc)",
        "arc-bright": "var(--arc-bright)",
        "arc-deep": "var(--arc-deep)",
        gold: "var(--gold)",
        "gold-bright": "var(--gold-bright)",
        "text-hi": "var(--text-hi)",
        "text-mid": "var(--text-mid)",
        "text-low": "var(--text-low)",
        ok: "var(--ok)",
        warn: "var(--warn)",
        danger: "var(--danger)",
      },
      fontFamily: {
        display: ["Orbitron", "sans-serif"],
        head: ["Rajdhani", "sans-serif"],
        body: ["Inter", "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
} satisfies Config;
