import { type Variants, motion } from "framer-motion";
import { useMemo, useState } from "react";
import { useResource } from "../../shared/api";
import { SERIES_NAME, int, pct } from "../../shared/format";
import type { BlackFriday, Series } from "../../shared/types";
import { EmptyState, ErrorState, Skeleton } from "../../shared/ui/states";
import { motionTokens } from "../../theme/motion";
import { chart, color } from "../../theme/tokens";

type Metric = "pods" | "errors" | "hit";
const METRICS: { key: Metric; label: string; fmt: (v: number) => string }[] = [
  { key: "pods", label: "PHP pods running", fmt: (v) => int(v) },
  { key: "errors", label: "Page views with a 5xx (per minute)", fmt: (v) => v.toFixed(1) },
  { key: "hit", label: "Served from the cache", fmt: (v) => pct(v, 0) },
];
const LINE: Record<string, string> = { shop_as_found: color.asFound, short_ttl: color.shortTtl, platform: color.platform };
const NAMES = ["shop_as_found", "short_ttl", "platform"];
/** The lines draw in when the metric changes (pathLength is an SVG-only motion value, hence the cast). */
const DRAW = { hidden: { pathLength: 0 }, shown: { pathLength: 1 } } as unknown as Variants;

export function BlackFridayView() {
  const r = useResource<BlackFriday>("/api/blackfriday");
  const [metric, setMetric] = useState<Metric>("pods");
  const [hover, setHover] = useState<number | null>(null);

  if (r.loading) return <Skeleton label="Loading Black Friday" rows={8} />;
  if (r.error || !r.data) return <ErrorState error={r.error!} retry={r.retry} what="the Black Friday replay" />;
  const names = NAMES.filter((n) => r.data!.series[n]);
  if (names.length === 0)
    return (
      <EmptyState title="No replay recorded">
        Run <code>python -m sep.eval.cli evaluate</code> to record Black Friday for the three main designs.
      </EmptyState>
    );
  return (
    <div className="flex flex-col gap-5">
      <div className="flex max-w-prose flex-col gap-2">
        <h1 className="text-title font-bold narrow">Black Friday, minute by minute</h1>
        <p className="text-muted">
          From 18:00 the evening before to midnight after the sale, in five-minute steps: the launch at midnight, 1,500
          products repriced at once, the evening peak and a slow search cluster at around 20:00.
        </p>
      </div>
      <div role="group" aria-label="Metric" className="flex flex-wrap gap-2">
        {METRICS.map((m) => (
          <button
            key={m.key}
            type="button"
            aria-pressed={metric === m.key}
            onClick={() => setMetric(m.key)}
            className={`rounded-pill border px-3 py-1 text-small font-semibold transition-colors ${
              metric === m.key ? "border-ink bg-ink text-sheet" : "border-line bg-sheet hover:border-ink"
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>
      <Chart data={r.data} names={names} metric={metric} hover={hover} setHover={setHover} />
    </div>
  );
}

/** Each point is one minute sampled every five; errors are page views with a 5xx in that minute. */
function values(s: Series, metric: Metric): number[] {
  return s[metric];
}

function Chart(props: {
  data: BlackFriday;
  names: string[];
  metric: Metric;
  hover: number | null;
  setHover: (i: number | null) => void;
}) {
  const { data, names, metric, hover, setHover } = props;
  const m = METRICS.find((x) => x.key === metric)!;
  const lines = useMemo(() => Object.fromEntries(names.map((n) => [n, values(data.series[n]!, metric)])), [data, names, metric]);
  const n = lines[names[0]!]!.length;
  const top = Math.max(...names.flatMap((k) => lines[k]!)) * 1.08 || 1;
  const { width: W, height: H, left: L, right: R, top: T, bottom: B } = chart;
  const x = (i: number) => L + ((W - L - R) * i) / Math.max(n - 1, 1);
  const y = (v: number) => T + (H - T - B) * (1 - v / top);
  // end labels: at each line's last value, pushed apart so two lines ending together stay readable
  const endY: Record<string, number> = {};
  [...names]
    .sort((a, b) => y(lines[a]![n - 1]!) - y(lines[b]![n - 1]!))
    .forEach((k, i, arr) => {
      const want = y(lines[k]![n - 1]!) + 4;
      const prev = i ? endY[arr[i - 1]!]! : -Infinity;
      endY[k] = Math.max(want, prev + 14);
    });
  const label = (i: number) => {
    const mins = 18 * 60 + i * data.step_minutes;
    return `${String(Math.floor(mins / 60) % 24).padStart(2, "0")}:${String(mins % 60).padStart(2, "0")}`;
  };
  const ticks = Array.from({ length: 5 }, (_, k) => (top / 1.08) * (k / 4));
  return (
    <figure className="flex flex-col gap-2 rounded-soft border border-line bg-sheet p-4">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`${m.label} on Black Friday for ${names.map((k) => SERIES_NAME[k]).join(", ")}`}
        onMouseLeave={() => setHover(null)}
        onMouseMove={(e) => {
          const box = e.currentTarget.getBoundingClientRect();
          const px = ((e.clientX - box.left) / box.width) * W;
          const i = Math.round(((px - L) / (W - L - R)) * (n - 1));
          setHover(i >= 0 && i < n ? i : null);
        }}
      >
        {ticks.map((v) => (
          <g key={v}>
            <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke={color.line} />
            <text x={L - 8} y={y(v) + 4} textAnchor="end" fontSize="11" fill={color.muted}>
              {m.fmt(v)}
            </text>
          </g>
        ))}
        {Array.from({ length: Math.floor(n / 36) + 1 }, (_, k) => k * 36).map((i) => (
          <text key={i} x={x(i)} y={H - 12} textAnchor="middle" fontSize="11" fill={color.muted}>
            {label(i)}
          </text>
        ))}
        {names.map((k) => {
          const d = lines[k]!.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");
          return (
            <g key={k}>
              <motion.path
                key={`${k}-${metric}`}
                d={d}
                fill="none"
                stroke={LINE[k]}
                strokeWidth={2}
                variants={DRAW}
                initial="hidden"
                animate="shown"
                transition={{ duration: motionTokens.draw, ease: motionTokens.ease }}
              />
              <text x={W - R + 8} y={endY[k]} fontSize="12" fill={color.ink}>
                {SERIES_NAME[k]}
              </text>
            </g>
          );
        })}
        {hover !== null && (
          <g>
            <line x1={x(hover)} x2={x(hover)} y1={T} y2={H - B} stroke={color.ink} strokeDasharray="3 3" />
            {names.map((k) => (
              <circle key={k} cx={x(hover)} cy={y(lines[k]![hover]!)} r={4} fill={LINE[k]} stroke={color.sheet} strokeWidth={2} />
            ))}
          </g>
        )}
      </svg>
      <figcaption className="flex min-h-6 flex-wrap gap-4 text-small" aria-live="polite">
        {hover === null ? (
          <span className="text-muted">Move over the chart to read the values at a moment.</span>
        ) : (
          <>
            <span className="font-semibold text-ink">{label(hover)}</span>
            {names.map((k) => (
              <span key={k} className="flex items-center gap-2">
                <span aria-hidden="true" className="size-swatch rounded-pill" style={{ background: LINE[k] }} />
                {SERIES_NAME[k]}: {m.fmt(lines[k]![hover]!)}
              </span>
            ))}
          </>
        )}
      </figcaption>
    </figure>
  );
}
