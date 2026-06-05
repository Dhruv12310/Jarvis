// Action buttons mapping 1:1 to the controller methods (Briefing, Agenda, Markets/News, Finance,
// Add Goal, Suggestions). Horizontally scrollable on narrow widths.
import type { ReactNode } from "react";
import ShortcutButton from "./ShortcutButton";

export interface ShortcutAction {
  id: string;
  label: string;
  icon: ReactNode;
  onClick: () => void;
  accent?: "arc" | "gold";
}

export default function ShortcutBar({ actions }: { actions: ShortcutAction[] }) {
  return (
    <div
      style={{
        display: "flex",
        gap: 10,
        overflowX: "auto",
        paddingBottom: 2,
      }}
    >
      {actions.map((a) => (
        <ShortcutButton
          key={a.id}
          icon={a.icon}
          label={a.label}
          onClick={a.onClick}
          accent={a.accent}
        />
      ))}
    </div>
  );
}
