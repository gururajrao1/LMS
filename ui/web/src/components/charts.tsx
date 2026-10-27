"use client";

/**
 * Chart primitives for the course reporting surfaces.
 *
 * Deliberately single-hue: every chart here encodes one measure, so length does
 * the work and no categorical palette is needed. Values are directly labelled in
 * ink rather than coloured, the brand mark beside them carries identity, and the
 * one place a second colour appears is a reserved status tint that always ships
 * with a written label rather than standing alone.
 */

const MARK = "var(--color-brand-600)";

export function ChartFrame({ title, note, children, className = "" }: {
  title: string;
  note?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-xl border border-line bg-white p-5 ${className}`}>
      <h3 className="text-base font-medium">{title}</h3>
      {note && <p className="mt-1 text-sm text-stone-600">{note}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

/** A horizontal bar with its label above and its value direct-labelled at the end. */
export function BarRow({ label, value, max, suffix = "", caption, tone = "brand", hint, display }: {
  label: string;
  value: number;
  max: number;
  suffix?: string;
  caption?: string;
  tone?: "brand" | "warning";
  hint?: string;
  /** Overrides the direct label when the number needs a prefix, like currency. */
  display?: string;
}) {
  const width = max > 0 ? Math.max(value > 0 ? 1.5 : 0, (100 * value) / max) : 0;
  return (
    <div className="group relative py-1.5" title={hint}>
      <div className="flex items-baseline justify-between gap-4">
        <span className="min-w-0 truncate text-sm text-stone-700">{label}</span>
        <span className="shrink-0 text-sm font-medium tabular-nums text-stone-700">
          {display ?? `${value}${suffix}`}{caption && <span className="ml-1.5 font-normal text-stone-600">{caption}</span>}
        </span>
      </div>
      <div className="mt-1.5 h-2 w-full rounded-full bg-stone-100">
        <div className="h-2 rounded-full transition-[width] duration-500"
          style={{ width: `${width}%`, background: tone === "warning" ? "var(--color-warn-600)" : MARK }} />
      </div>
    </div>
  );
}

/** Vertical columns for a distribution, direct-labelled above each column. */
export function ColumnChart({ data, unit = "" }: { data: { label: string; value: number }[]; unit?: string }) {
  const max = Math.max(1, ...data.map((entry) => entry.value));
  return (
    <div className="flex items-end gap-2" style={{ height: 150 }}>
      {data.map((entry) => (
        <div key={entry.label} className="flex flex-1 flex-col items-center justify-end gap-2" title={`${entry.label}: ${entry.value}${unit}`}>
          <span className="text-sm font-medium tabular-nums text-stone-700">{entry.value}</span>
          <div className="w-full rounded-t-[4px] transition-[height] duration-500"
            style={{ height: `${Math.max(entry.value > 0 ? 4 : 2, (100 * entry.value) / max)}%`, minHeight: entry.value > 0 ? 6 : 2, background: entry.value > 0 ? MARK : "var(--color-line)" }} />
          <span className="text-xs text-stone-600">{entry.label}</span>
        </div>
      ))}
    </div>
  );
}

/**
 * Small multiples: one row per measure, each its own single-hue scale. Three
 * measures over the same dates would otherwise need a categorical palette or a
 * second axis, and both are worse than three honest rows.
 */
export function ActivityGrid({ series }: { series: { date: string; rows: { label: string; values: number[] }[] } }) {
  const { date, rows } = series;
  return (
    <div className="space-y-4">
      {rows.map((row) => {
        const max = Math.max(1, ...row.values);
        return (
          <div key={row.label}>
            <div className="flex items-baseline justify-between">
              <span className="text-sm text-stone-700">{row.label}</span>
              <span className="text-sm font-medium tabular-nums text-stone-700">{row.values.reduce((a, b) => a + b, 0)}</span>
            </div>
            <div className="mt-1.5 flex h-8 items-end gap-1">
              {row.values.map((value, index) => (
                <div key={index} className="flex-1 rounded-t-[3px]" title={`${value}`}
                  style={{ height: `${Math.max(value > 0 ? 12 : 4, (100 * value) / max)}%`, background: value > 0 ? MARK : "var(--color-line)" }} />
              ))}
            </div>
          </div>
        );
      })}
      <p className="text-xs text-stone-600">{date}</p>
    </div>
  );
}

/** Baseline → final for a whole cohort: one bar, with the starting point marked. */
export function UpliftMeter({ baseline, final, label }: { baseline: number; final: number; label?: string }) {
  return (
    <div>
      <div className="relative h-3 w-full rounded-full bg-stone-100">
        <div className="h-3 rounded-full" style={{ width: `${final}%`, background: MARK }} />
        <span aria-hidden className="absolute top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-stone-500 ring-2 ring-white"
          style={{ left: `calc(${baseline}% - 1px)` }} />
      </div>
      <div className="mt-2 flex items-baseline justify-between text-sm">
        <span className="text-stone-600">Baseline <b className="tabular-nums text-stone-800">{baseline}%</b></span>
        <span className="text-stone-600">Final <b className="tabular-nums text-stone-800">{final}%</b></span>
      </div>
      {label && <p className="mt-1 text-xs text-stone-600">{label}</p>}
    </div>
  );
}

/**
 * Two stacked bars on one shared scale: what a process actually took, against
 * what it takes by hand. A shared scale is the whole point — the comparison is
 * the message, and two independently-scaled bars would flatter the shorter one.
 * Segments are separated by a 2px surface gap and labelled directly.
 */
export function PhaseComparison({ phases, measuredTotal, manualTotal, format }: {
  phases: { phase: string; detail: string; measured_days: number | null; manual_days: number }[];
  measuredTotal: number;
  manualTotal: number;
  format: (days: number | null) => string;
}) {
  const scale = Math.max(measuredTotal, manualTotal, 1);
  const steps = ["var(--color-brand-700)", "var(--color-brand-500)", "var(--color-brand-400)", "var(--color-brand-200)"];

  // Both bars use the same four hues so a segment can be matched across them at a
  // glance; the manual row is dimmed rather than recoloured, because a different
  // palette would break that correspondence.
  const bar = (label: string, total: number, value: (index: number) => number | null, muted: boolean) => (
    <div>
      <div className="flex items-baseline justify-between gap-4">
        <span className="text-sm font-medium text-stone-700">{label}</span>
        <span className="text-sm font-semibold tabular-nums">{format(total)}</span>
      </div>
      <div className="mt-2 flex h-7 w-full gap-0.5 overflow-hidden rounded-md bg-stone-100">
        {phases.map((phase, index) => {
          const days = value(index) ?? 0;
          return (
            <div key={phase.phase} title={`${phase.phase}: ${format(value(index))}`}
              style={{
                width: `${(100 * days) / scale}%`,
                background: steps[index % steps.length],
                opacity: muted ? 0.4 : 1,
              }} />
          );
        })}
      </div>
    </div>
  );

  return (
    <div className="space-y-5">
      {bar("With PharmaLearn", measuredTotal, (index) => phases[index].measured_days, false)}
      {bar("The same work, done manually", manualTotal, (index) => phases[index].manual_days, true)}

      <div className="space-y-2 border-t pt-4">
        {phases.map((phase, index) => (
          <div key={phase.phase} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-sm">
            <span aria-hidden className="size-2.5 shrink-0 translate-y-px rounded-[2px]" style={{ background: steps[index % steps.length] }} />
            <span className="font-medium text-stone-700">{phase.phase}</span>
            <span className="ml-auto tabular-nums text-stone-700">
              <b>{format(phase.measured_days)}</b>
              <span className="text-stone-500"> vs {format(phase.manual_days)} manually</span>
            </span>
            <p className="w-full pl-[1.375rem] text-xs leading-5 text-stone-600">{phase.detail}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
