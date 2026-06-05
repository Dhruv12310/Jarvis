// Tabular-mono live clock; ticks once per second.
import { useEffect, useState } from "react";

function fmt(d: Date, showSeconds: boolean): string {
  const p = (n: number) => String(n).padStart(2, "0");
  const hms = `${p(d.getHours())}:${p(d.getMinutes())}`;
  return showSeconds ? `${hms}:${p(d.getSeconds())}` : hms;
}

export default function Clock({ showSeconds = true }: { showSeconds?: boolean }) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return (
    <span
      className="tabular"
      style={{
        fontFamily: "var(--font-mono)",
        fontSize: 15,
        color: "var(--text-mid)",
        letterSpacing: "0.04em",
      }}
    >
      {fmt(now, showSeconds)}
    </span>
  );
}
