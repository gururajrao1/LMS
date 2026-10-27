"use client";

import { Figure } from "@/lib/api";

/**
 * The chart a figure question is asked about.
 *
 * Rendered from the numbers the agent cited, not from an image file. That is the
 * honest form of "show them a picture": a photograph, scan or histology slide
 * would need licensing we do not have, and a wrong or unrepresentative one is a
 * clinical error no check of ours could catch. Every value here traces to a
 * source, and the checker reads the question like any other.
 *
 * Two series are told apart by name, line style and marker as well as colour, so
 * a reader who cannot separate the hues loses nothing. Each series is labelled
 * where it ends rather than in a legend box, and a table of the same numbers sits
 * underneath — the chart is never the only way to get the values.
 */

const SERIES = [
  { stroke: "var(--color-brand-600)", fill: "var(--color-brand-600)", dash: "", marker: "circle" },
  { stroke: "var(--color-signal-600)", fill: "var(--color-signal-600)", dash: "6 4", marker: "square" },
] as const;

const WIDTH = 620;
const HEIGHT = 268;
// Room on the right only when something is written there: line charts label each
// series where it ends, and multi-series bars need a key. A single-series bar
// chart reserving that space just renders a third of the frame empty.
const gutter = (kind: string, series: number) => (kind === "line" || series > 1 ? 132 : 16);
const PAD = { top: 30, bottom: 46, left: 52 };

function ticks(max: number) {
  const step = max <= 5 ? 1 : max <= 20 ? 5 : max <= 60 ? 10 : max <= 120 ? 25 : 50;
  const out: number[] = [];
  for (let value = 0; value <= max; value += step) out.push(value);
  if (out[out.length - 1] !== max) out.push(max);
  return out;
}

export function QuizFigure({ figure }: { figure: Figure }) {
  const labels = figure.series[0]?.points.map((point) => point.label) ?? [];
  const values = figure.series.flatMap((series) => series.points.map((point) => point.value));
  const top = Math.max(...values, 1);
  const max = top <= 1 ? 1 : Math.ceil(top * 1.1);
  const right = gutter(figure.chart_kind, figure.series.length);
  const plotW = WIDTH - PAD.left - right;
  const plotH = HEIGHT - PAD.top - PAD.bottom;
  const y = (value: number) => PAD.top + plotH - (value / max) * plotH;
  const x = (index: number) =>
    labels.length < 2 ? PAD.left + plotW / 2 : PAD.left + (index / (labels.length - 1)) * plotW;

  const bars = figure.chart_kind === "bar";
  const slot = plotW / Math.max(labels.length, 1);
  const barW = Math.min(38, (slot * 0.7) / Math.max(figure.series.length, 1));

  return (
    <figure className="mt-1">
      <div className="overflow-x-auto rounded-lg border bg-white p-3">
        <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} width={WIDTH} height={HEIGHT}
          role="img" aria-label={figure.caption} className="h-auto max-w-full">
          {ticks(max).map((tick) => (
            <g key={tick}>
              <line x1={PAD.left} x2={WIDTH - right} y1={y(tick)} y2={y(tick)}
                stroke="var(--color-stone-200, #e7e5e4)" strokeWidth={1} />
              <text x={PAD.left - 8} y={y(tick) + 4} textAnchor="end"
                className="fill-stone-500 text-[11px] tabular-nums">{tick}</text>
            </g>
          ))}

          {labels.map((label, index) => (
            <text key={label} x={bars ? PAD.left + slot * (index + 0.5) : x(index)} y={HEIGHT - PAD.bottom + 18}
              textAnchor="middle" className="fill-stone-600 text-[11px]">{label}</text>
          ))}

          {figure.series.map((series, seriesIndex) => {
            const style = SERIES[seriesIndex % SERIES.length];
            if (bars) {
              return (
                <g key={series.name}>
                  {series.points.map((point, index) => {
                    const centre = PAD.left + slot * (index + 0.5);
                    const offset = (seriesIndex - (figure.series.length - 1) / 2) * (barW + 2);
                    return (
                      <rect key={point.label} x={centre + offset - barW / 2} y={y(point.value)}
                        width={barW} height={Math.max(plotH - (y(point.value) - PAD.top), 2)}
                        rx={4} fill={style.fill}
                        // A 2px surface gap so adjacent bars never read as one mark.
                        stroke="white" strokeWidth={2} />
                    );
                  })}
                </g>
              );
            }
            const path = series.points.map((point, index) => `${index ? "L" : "M"}${x(index)},${y(point.value)}`).join(" ");
            const last = series.points[series.points.length - 1];
            return (
              <g key={series.name}>
                <path d={path} fill="none" stroke={style.stroke} strokeWidth={2}
                  strokeDasharray={style.dash} strokeLinecap="round" strokeLinejoin="round" />
                {series.points.map((point, index) => (
                  style.marker === "square" ? (
                    <rect key={point.label} x={x(index) - 4} y={y(point.value) - 4} width={8} height={8}
                      fill={style.fill} stroke="white" strokeWidth={2} />
                  ) : (
                    <circle key={point.label} cx={x(index)} cy={y(point.value)} r={4.5}
                      fill={style.fill} stroke="white" strokeWidth={2} />
                  )
                ))}
                {last && (
                  <text x={x(series.points.length - 1) + 10} y={y(last.value) + 4}
                    className="fill-stone-700 text-[11px] font-medium">{series.name}</text>
                )}
              </g>
            );
          })}

          {bars && figure.series.length > 1 && figure.series.map((series, seriesIndex) => (
            <g key={series.name}>
              <rect x={WIDTH - right + 8} y={PAD.top + seriesIndex * 20} width={10} height={10} rx={2}
                fill={SERIES[seriesIndex % SERIES.length].fill} />
              <text x={WIDTH - right + 24} y={PAD.top + seriesIndex * 20 + 9}
                className="fill-stone-700 text-[11px]">{series.name}</text>
            </g>
          ))}

          <line x1={PAD.left} x2={WIDTH - right} y1={y(0)} y2={y(0)}
            stroke="var(--color-stone-300, #d6d3d1)" strokeWidth={1} />
          <text x={PAD.left} y={HEIGHT - 6} className="fill-stone-500 text-[11px]">{figure.x_title}</text>
          {/* Above the plot and anchored to the left edge. Right-anchored beside
              the tick labels, any title longer than the 52px left pad ran off the
              frame — "Median progression-free survival" rendered as "vival mo". */}
          <text x={4} y={14} className="fill-stone-500 text-[11px]">
            {figure.y_title}{figure.y_suffix ? ` (${figure.y_suffix.trim()})` : ""}
          </text>
        </svg>
      </div>

      <figcaption className="mt-2 text-xs leading-5 text-stone-600">{figure.caption}</figcaption>

      {/* The same numbers as text. A chart that is the only route to the values
          is unreadable to a screen reader and unusable in a printed pack. */}
      <details className="mt-2">
        <summary className="cursor-pointer text-xs font-medium text-stone-600 hover:text-brand-700">
          Show these values as a table
        </summary>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b text-left text-stone-600">
                <th className="py-1 pr-3 font-medium">{figure.x_title}</th>
                {figure.series.map((series) => (
                  <th key={series.name} className="py-1 pr-3 text-right font-medium">{series.name}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {labels.map((label, index) => (
                <tr key={label} className="border-b last:border-0">
                  <td className="py-1 pr-3 text-stone-700">{label}</td>
                  {figure.series.map((series) => (
                    <td key={series.name} className="py-1 pr-3 text-right tabular-nums text-stone-700">
                      {series.points[index]?.value ?? "—"}{figure.y_suffix}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}
