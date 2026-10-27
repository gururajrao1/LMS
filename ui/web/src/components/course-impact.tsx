"use client";

import { useEffect, useState } from "react";
import { CalendarClock, CircleDollarSign, FileCheck2, Gauge, Info, MessageSquareQuote, Star, TriangleAlert } from "lucide-react";
import { ActivityGrid, BarRow, ChartFrame, ColumnChart, PhaseComparison, UpliftMeter } from "@/components/charts";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Analytics, Cohort, getJson } from "@/lib/api";

const NEEDS_REVIEW = 60;

function money(value: number) {
  return `$${value.toLocaleString("en-US")}`;
}

function elapsed(minutes: number | null) {
  if (minutes === null) return "–";
  if (minutes < 1) return `${Math.round(minutes * 60)} sec`;
  if (minutes < 90) return `${Math.round(minutes)} min`;
  return `${(minutes / 60).toFixed(1)} hrs`;
}

function Hero({ roi }: { roi: Analytics["roi"] }) {
  const { measured, baseline, saving } = roi;
  return (
    <Card className="overflow-hidden p-0">
      <div className="bg-surface-deep p-6 text-white md:p-8">
        <p className="text-xs font-semibold uppercase tracking-[.16em] text-brand-300">Time to field</p>
        <div className="mt-4 flex flex-wrap items-end gap-x-10 gap-y-6">
          <div>
            <p className="text-5xl font-semibold tabular-nums">{saving.percent_faster ?? "–"}%</p>
            <p className="mt-1 text-sm text-stone-300">faster than the manual baseline</p>
          </div>
          <div>
            <p className="text-3xl font-semibold tabular-nums">{duration(measured.days_to_publish)}</p>
            <p className="mt-1 text-sm text-stone-300">generated, reviewed and published</p>
          </div>
          <div>
            <p className="text-3xl font-semibold tabular-nums">{baseline.first_version_days} <span className="text-lg font-normal text-stone-300">days</span></p>
            <p className="mt-1 text-sm text-stone-300">the same work, done manually</p>
          </div>
          <div>
            <p className="text-3xl font-semibold tabular-nums">{saving.cost_saved_usd === null ? "–" : money(saving.cost_saved_usd)}</p>
            <p className="mt-1 text-sm text-stone-300">effort saved on this course</p>
          </div>
        </div>
      </div>
      <CardContent className="grid gap-4 p-6 sm:grid-cols-2 xl:grid-cols-4">
        {[
          { icon: Gauge, label: "Draft generated in", value: elapsed(measured.generation_minutes) },
          { icon: CalendarClock, label: "Expert review cycle", value: duration(measured.review_days) },
          { icon: MessageSquareQuote, label: "Expert comments across " + measured.versions + " versions", value: measured.expert_comments },
          { icon: FileCheck2, label: "Traceable citations", value: measured.citations ?? "–" },
        ].map((item) => (
          <div key={item.label} className="flex items-start gap-3">
            <span className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-xl bg-brand-50 text-brand-700"><item.icon size={18} /></span>
            <div><p className="text-xl font-semibold tabular-nums">{item.value}</p><p className="text-sm text-stone-600">{item.label}</p></div>
          </div>
        ))}
      </CardContent>
      <div className="flex items-start gap-2 border-t bg-stone-50 px-6 py-4 text-xs leading-5 text-stone-600">
        <Info size={14} className="mt-0.5 shrink-0" />
        <p>
          Elapsed time, review cycle, comment count and citations are measured from this course&apos;s own run and review logs.
          The comparison assumes a manual first version takes {baseline.first_version_days} days and a blended day rate of{" "}
          {money(baseline.blended_day_rate_usd)}; agent spend on this run was {money(measured.agent_cost_usd)}. Change those
          assumptions and the saving moves with them.
        </p>
      </div>
    </Card>
  );
}

/** Days, but readable — a generation step that took ten seconds is not "0.0 days". */
function duration(days: number | null) {
  if (days === null) return "–";
  const minutes = days * 1440;
  if (minutes < 1) return `${Math.max(1, Math.round(minutes * 60))} sec`;
  if (minutes < 90) return `${Math.round(minutes)} min`;
  if (days < 1) return `${Math.round(minutes / 60)} hrs`;
  return `${days % 1 === 0 ? days : days.toFixed(1)} days`;
}

/**
 * Cost per certified learner, and the curve behind it.
 *
 * Building a course is a fixed cost, so the per-learner figure is really a
 * statement about audience size. Showing only today's number invites the wrong
 * conclusion; showing the curve makes the actual lever obvious.
 */
function UnitEconomics({ economics, rate, days }: { economics: Analytics["unit_economics"]; rate: number; days: number | null }) {
  const best = Math.max(...economics.curve.map((point) => point.manual_cost_usd ?? 0), 1);
  return (
    <ChartFrame title="Cost per certified learner"
      note={`Build cost spread across the people certified on it. Fixed cost, so it falls as the cohort grows.`}>
      <div className="flex flex-wrap items-end gap-x-8 gap-y-3">
        <div>
          <p className="text-4xl font-semibold tabular-nums">{economics.cost_per_certified_usd === null ? "–" : money(economics.cost_per_certified_usd)}</p>
          <p className="mt-1 text-sm text-stone-600">now, across {economics.certified} certified</p>
        </div>
        <div>
          <p className="text-2xl font-semibold tabular-nums text-stone-500">{economics.manual_cost_per_certified_usd === null ? "–" : money(economics.manual_cost_per_certified_usd)}</p>
          <p className="mt-1 text-sm text-stone-600">the same course, built by hand</p>
        </div>
      </div>

      <div className="mt-5 space-y-2.5 border-t pt-4">
        {economics.curve.map((point) => (
          <div key={point.learners}>
            <div className="flex items-baseline justify-between gap-4 text-sm">
              <span className="text-stone-700">
                {point.learners} learner{point.learners === 1 ? "" : "s"}
                {point.measured
                  ? <span className="ml-2 text-xs font-medium text-brand-700">measured</span>
                  : <span className="ml-2 text-xs text-stone-500">projected</span>}
              </span>
              <span className="font-medium tabular-nums">{point.cost_usd === null ? "–" : money(point.cost_usd)}</span>
            </div>
            <div className="mt-1 h-2 w-full rounded-full bg-stone-100">
              <div className="h-2 rounded-full" style={{
                width: `${Math.max(1.5, (100 * (point.cost_usd ?? 0)) / best)}%`,
                background: point.measured ? "var(--color-brand-600)" : "var(--color-brand-300)",
              }} />
            </div>
          </div>
        ))}
      </div>

      <p className="mt-4 text-xs leading-5 text-stone-600">
        Build cost is {money(economics.build_cost_usd)}: {economics.expert_days_costed} days of expert effort at{" "}
        {money(rate)}/day plus agent spend.{" "}
        {economics.floored
          ? `This course reached the field in ${duration(days)}, which is too little elapsed time to cost meaningfully — it is costed at the ${economics.expert_days_costed}-day minimum of expert attention instead.`
          : "Elapsed effort is measured from this course's own run and review logs."}{" "}
        Only the first row is measured; the rest divide that same fixed cost across a larger audience.
      </p>
    </ChartFrame>
  );
}

/** How quickly the field actually became able to use the material. */
function SpeedToCompetence({ speed }: { speed: Analytics["speed_to_competence"] }) {
  const scale = Math.max(speed.slowest_days ?? 1, 1);
  return (
    <ChartFrame title="Speed to competence"
      note="Days from the course reaching the field to each learner being certified.">
      <div className="flex flex-wrap items-end gap-x-8 gap-y-3">
        <div>
          <p className="text-4xl font-semibold tabular-nums">{speed.median_days ?? "–"}<span className="ml-1.5 text-lg font-normal text-stone-600">days</span></p>
          <p className="mt-1 text-sm text-stone-600">median, {speed.certified} certified</p>
        </div>
        {speed.outstanding > 0 && (
          <div>
            <p className="text-2xl font-semibold tabular-nums text-stone-500">{speed.outstanding}</p>
            <p className="mt-1 text-sm text-stone-600">still outstanding</p>
          </div>
        )}
      </div>

      <div className="mt-5 space-y-2.5 border-t pt-4">
        {speed.learners.map((learner) => (
          <div key={learner.name}>
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span className="min-w-0 truncate text-stone-700">{learner.name} <span className="text-xs text-stone-500">{learner.track}</span></span>
              <span className="shrink-0 tabular-nums text-stone-700">
                {learner.days === null
                  ? <span className="text-stone-500">not yet certified</span>
                  : <>{learner.days} days{learner.attempts > 1 && <span className="ml-1.5 text-xs text-stone-500">{learner.attempts} attempts</span>}</>}
              </span>
            </div>
            <div className="mt-1 h-2 w-full rounded-full bg-stone-100">
              {learner.days !== null && (
                <div className="h-2 rounded-full" style={{ width: `${Math.max(2, (100 * learner.days) / scale)}%`, background: "var(--color-brand-600)" }} />
              )}
            </div>
          </div>
        ))}
      </div>
    </ChartFrame>
  );
}

/** What the automated pre-review took off the reviewers' desks. */
function CheckerLeverage({ leverage }: { leverage: Analytics["checker_leverage"] }) {
  return (
    <ChartFrame title="Review effort the checker absorbed"
      note="Machine findings the experts agreed with. A dismissed finding saved nobody anything and is not counted.">
      <div className="flex flex-wrap items-end gap-x-8 gap-y-3">
        <div>
          <p className="text-4xl font-semibold tabular-nums">{leverage.reviewer_hours_saved}<span className="ml-1.5 text-lg font-normal text-stone-600">hrs</span></p>
          <p className="mt-1 text-sm text-stone-600">of expert reading, at {leverage.minutes_per_defect} min per defect</p>
        </div>
        <div>
          <p className="text-2xl font-semibold tabular-nums text-stone-500">{leverage.agreement_percent === null ? "–" : `${leverage.agreement_percent}%`}</p>
          <p className="mt-1 text-sm text-stone-600">
            {leverage.agreement_percent === null
              ? `of its findings accepted — withheld until ${leverage.min_for_rate} are settled`
              : "of its findings were accepted"}
          </p>
        </div>
      </div>

      <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-3 border-t pt-4 text-sm sm:grid-cols-3">
        {[
          ["Units checked", leverage.units_checked ?? "–"],
          ["Quotes verifiable", leverage.citations_checked ?? "–"],
          ["Findings raised", leverage.raised],
          ["Accepted by experts", leverage.accepted],
          ["Dismissed", leverage.dismissed],
          ["Raised by people", leverage.human_comments],
        ].map(([label, value]) => (
          <div key={label as string}>
            <dt className="text-stone-600">{label}</dt>
            <dd className="text-lg font-semibold tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
    </ChartFrame>
  );
}

export function CourseImpactPanel({ runId }: { runId: string }) {
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [cohort, setCohort] = useState<Cohort | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getJson<Analytics>(`/api/runs/${runId}/analytics`).then(setAnalytics).catch(() => setError("Could not load analytics."));
    getJson<Cohort>(`/api/runs/${runId}/cohort`).then(setCohort).catch(() => undefined);
  }, [runId]);

  if (!analytics) return <Card><CardContent className="p-8 text-center text-stone-600">{error || "Loading impact…"}</CardContent></Card>;
  if (analytics.roi.measured.days_to_publish === null) {
    return <Card><CardContent className="p-8 text-center text-stone-600">Publish this course to measure its impact.</CardContent></Card>;
  }

  const funnelMax = analytics.funnel[0]?.count ?? 1;
  const hardest = analytics.difficulty.slice(0, 6);
  const flagged = analytics.difficulty.filter((entry) => entry.percent < NEEDS_REVIEW).length;
  const dates = analytics.activity.map((entry) => entry.date);

  return (
    <div className="space-y-5">
      <Hero roi={analytics.roi} />

      <div className="grid gap-5 lg:grid-cols-2">
        <ChartFrame title="Where the three days went"
          note="The headline number, split by phase and set against the same work done by hand.">
          <PhaseComparison phases={analytics.time_to_field.phases} format={duration}
            measuredTotal={analytics.time_to_field.measured_total_days}
            manualTotal={analytics.time_to_field.manual_total_days} />
        </ChartFrame>

        <UnitEconomics economics={analytics.unit_economics} rate={analytics.roi.baseline.blended_day_rate_usd} days={analytics.roi.measured.days_to_publish} />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <SpeedToCompetence speed={analytics.speed_to_competence} />
        <CheckerLeverage leverage={analytics.checker_leverage} />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <ChartFrame title="Completion funnel" note="How far the assigned cohort has progressed.">
          <div className="space-y-1">
            {analytics.funnel.map((stage) => (
              <BarRow key={stage.stage} label={stage.stage} value={stage.count} max={funnelMax}
                caption={`${stage.percent}%`} hint={`${stage.count} of ${funnelMax} learners`} />
            ))}
          </div>
        </ChartFrame>

        <ChartFrame title="Knowledge uplift" note={cohort ? `Averaged over the ${cohort.measured} learner${cohort.measured === 1 ? "" : "s"} who have taken both assessments.` : undefined}>
          {cohort?.average_baseline !== null && cohort?.average_final !== null && cohort ? (
            <div className="space-y-5">
              <UpliftMeter baseline={cohort.average_baseline!} final={cohort.average_final!}
                label={`The same cohort, measured before and after the course.`} />
              <div className="rounded-xl bg-brand-50 p-4">
                <p className="text-3xl font-semibold tabular-nums text-ink">+{cohort.average_uplift}</p>
                <p className="mt-1 text-sm text-stone-600">percentage points gained per learner</p>
              </div>

              {/* One cohort average hides the case the two tracks exist to handle. */}
              {analytics.uplift_by_track.length > 1 && (
                <div className="space-y-3 border-t pt-4">
                  <p className="text-sm font-medium text-stone-700">By track</p>
                  {analytics.uplift_by_track.map((entry) => (
                    <div key={entry.track} className="flex items-baseline justify-between gap-4 text-sm">
                      <span className="text-stone-700">
                        {entry.track} <span className="text-xs text-stone-500">{entry.learners} learner{entry.learners === 1 ? "" : "s"}</span>
                      </span>
                      <span className="tabular-nums text-stone-700">
                        {entry.baseline} → <b>{entry.final}</b>
                        <span className="ml-2 font-medium text-brand-700">+{entry.uplift}</span>
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : <p className="py-8 text-center text-stone-600">No learner has completed both assessments yet.</p>}
        </ChartFrame>

        <ChartFrame title="Final score distribution" note="Where the cohort landed on the graded assessment.">
          <ColumnChart data={analytics.score_bands.map((band) => ({ label: band.band, value: band.count }))} />
        </ChartFrame>

        <ChartFrame title="Activity since publication" note={`Daily learning actions from ${dates[0] ?? "–"} to ${dates[dates.length - 1] ?? "–"}.`}>
          {analytics.activity.length ? (
            <ActivityGrid series={{
              date: `${dates.length} active day${dates.length === 1 ? "" : "s"}`,
              rows: [
                { label: "Modules completed", values: analytics.activity.map((entry) => entry.modules) },
                { label: "Assessments taken", values: analytics.activity.map((entry) => entry.assessments) },
                { label: "Certificates issued", values: analytics.activity.map((entry) => entry.certificates) },
              ],
            }} />
          ) : <p className="py-8 text-center text-stone-600">No learner activity recorded yet.</p>}
        </ChartFrame>
      </div>

      <ChartFrame
        title="Hardest questions"
        note="Scored from the cohort's answers on the graded assessment. A question most learners miss is usually a gap in the material, not the learner.">
        {hardest.length ? (
          <>
            {flagged > 0 && (
              <p className="mb-3 inline-flex items-center gap-2 rounded-lg bg-warn-50 px-3 py-2 text-sm text-warn-700">
                <TriangleAlert size={15} /> {flagged} question{flagged === 1 ? "" : "s"} below {NEEDS_REVIEW}% — worth revisiting in the next version
              </p>
            )}
            <div className="space-y-1">
              {hardest.map((entry) => (
                <BarRow key={`${entry.track}-${entry.id}`} label={entry.prompt} value={entry.percent} max={100} suffix="%"
                  tone={entry.percent < NEEDS_REVIEW ? "warning" : "brand"}
                  caption={`${entry.correct}/${entry.attempts} correct · ${entry.track.toUpperCase()}`}
                  hint={entry.prompt} />
              ))}
            </div>
          </>
        ) : <p className="py-8 text-center text-stone-600">No graded answers recorded yet.</p>}
      </ChartFrame>

      <ChartFrame title="Module engagement" note="Completions and the rating learners gave each module.">
        <div className="space-y-1">
          {analytics.modules.map((module) => (
            <BarRow key={module.id} label={`${module.title} · ${module.minutes} min`} value={module.completed} max={funnelMax}
              caption={module.rating ? `★ ${module.rating} (${module.ratings})` : "no ratings yet"} />
          ))}
        </div>
      </ChartFrame>

      {cohort && cohort.feedback.length > 0 && (
        <ChartFrame title="What learners said" note="Direct feedback, newest first.">
          <div className="space-y-3">
            {cohort.feedback.map((entry) => (
              <div key={entry.id} className="rounded-xl border p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-sm font-medium">{entry.name}</p>
                  <Badge variant="outline" className="capitalize">{entry.module_id}</Badge>
                  <span className="ml-auto inline-flex items-center gap-1 text-sm tabular-nums text-stone-700">
                    <Star size={14} className="fill-warn-400 text-warn-500" /> {entry.rating}/5
                  </span>
                </div>
                {entry.comment && <p className="mt-2 leading-6 text-stone-700">{entry.comment}</p>}
              </div>
            ))}
          </div>
        </ChartFrame>
      )}

      <p className="flex items-center gap-2 text-xs text-stone-600">
        <CircleDollarSign size={14} /> Updating this course when the label changes is estimated to save a further{" "}
        {analytics.roi.saving.update_days_saved} days of manual effort per revision.
      </p>
    </div>
  );
}
