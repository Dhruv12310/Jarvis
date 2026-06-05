// A single eDEX micro-stat row: mono LABEL ···· VALUE with a dotted leader. `trend` colors the value
// (--up/--down/--idle). Used by the StatusBar's telemetry-lite cluster.
export default function Telemetry({
  label,
  value,
  trend = "none",
}: {
  label: string;
  value: string;
  trend?: "up" | "down" | "idle" | "none";
}) {
  return (
    <div className="telemetry">
      <span className="t-label">{label}</span>
      <span className="t-dots" />
      <span className={`t-value${trend === "none" ? "" : ` ${trend}`}`}>{value}</span>
    </div>
  );
}
