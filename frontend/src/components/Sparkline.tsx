// Pure-SVG sparkline. Draws a polyline from a short price series into a fixed viewBox - no chart lib,
// no history endpoint. The series is built CLIENT-SIDE from successive /api/quotes polls (App holds
// the last N prices per symbol). Color/sign is set by the parent toggling .hud-spark.is-up/.is-down.
// Below MIN_POINTS the caller shows "warming up" instead of rendering this.
const W = 96;
const H = 28;
const PAD = 3;

export default function Sparkline({ values }: { values: number[] }) {
  const n = values.length;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min;

  const x = (i: number) => (n === 1 ? 0 : (i / (n - 1)) * W);
  const y = (p: number) => (span === 0 ? H / 2 : PAD + (1 - (p - min) / span) * (H - 2 * PAD));

  const points = values.map((p, i) => `${x(i).toFixed(2)},${y(p).toFixed(2)}`).join(" ");
  // Area fill: the line, then down the right edge, across the bottom, up the left edge - closed.
  const fillPath =
    `M ${x(0).toFixed(2)},${y(values[0]).toFixed(2)} ` +
    values.map((p, i) => `L ${x(i).toFixed(2)},${y(p).toFixed(2)}`).join(" ") +
    ` L ${W},${H} L 0,${H} Z`;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden="true">
      <path className="spark-fill" d={fillPath} />
      <polyline className="spark-stroke" points={points} />
    </svg>
  );
}
