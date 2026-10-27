"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Award, CalendarClock, Coins, Printer, ScanLine, ShieldCheck, TrendingUp, Users } from "lucide-react";
import { AppShell, Loading, Stat } from "@/components/app-shell";
import { BarRow, ChartFrame, UpliftMeter } from "@/components/charts";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Client, getJson, Portfolio } from "@/lib/api";
import { useSession } from "@/lib/session";

const money = (value: number | null | undefined) =>
  value === null || value === undefined ? "–" : `$${value.toLocaleString("en-US")}`;

export default function PortfolioPage() {
  const user = useSession(["admin", "reviewer"]);
  const [data, setData] = useState<Portfolio | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getJson<Client[]>("/api/clients")
      .then((clients) => getJson<Portfolio>(`/api/clients/${clients[0].id}/portfolio`))
      .then(setData)
      .catch(() => setError("Could not load the portfolio."));
  }, []);

  if (!user) return <AppShell><Loading /></AppShell>;
  if (!data) return <AppShell user={user}>{error ? <p className="text-sm text-danger-600">{error}</p> : <Loading />}</AppShell>;

  const { reach, uplift, speed, cost, governance } = data;
  const live = data.states.live + data.states.scheduled;

  return (
    <AppShell user={user}>
      <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
        <div>
          <p className="text-sm font-semibold text-brand-700">CLIENT PORTFOLIO</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">{data.client.name}</h1>
          <p className="mt-2 text-stone-600">
            Every training programme delivered for {data.client.name}, consolidated. {data.programmes.length} programme
            {data.programmes.length === 1 ? "" : "s"} · {live} currently running · {data.client.region}.
          </p>
          {/* Only in the PDF: whoever opens the file was not in the room, so it has
              to say what it is, when it was taken and where the numbers came from. */}
          <p className="print-only mt-3 text-sm text-stone-600">
            Generated {new Date().toLocaleDateString(undefined, { dateStyle: "long" })} from the PharmaLearn
            workspace · measured, not modelled · {data.client.jurisdiction} regulatory scope
          </p>
        </div>
        <Button variant="outline" className="no-print shrink-0" onClick={() => window.print()}>
          <Printer /> Export PDF
        </Button>
      </div>

      <section className="print-keep mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat icon={Award} value={reach.certified} label={`Certified of ${reach.assigned} assigned`} />
        <Stat icon={TrendingUp} value={uplift.points === null ? "–" : `+${uplift.points}`} label="Points gained, pooled over learners" />
        <Stat icon={CalendarClock} value={speed.median_days_to_publish ?? "–"} label="Median days to field" tone="signal" />
        <Stat icon={Coins} value={money(cost.per_certified_usd)} label="Cost per certified learner" />
      </section>

      <div className="mt-5 grid items-start gap-5 lg:grid-cols-2">
        <ChartFrame className="print-keep" title="Time to the field"
          note={`Measured across ${speed.programmes} programme${speed.programmes === 1 ? "" : "s"}, against the stated manual baseline.`}>
          <BarRow label="With PharmaLearn" value={speed.median_days_to_publish ?? 0} max={speed.manual_days} suffix=" days" />
          <BarRow label="The same work, done manually" value={speed.manual_days} max={speed.manual_days} suffix=" days" tone="warning" />
        </ChartFrame>

        <ChartFrame className="print-keep" title="Cost per certified learner"
          note="Build cost is elapsed days at the blended rate plus what the agent actually spent, divided by the people who finished.">
          <BarRow label="With PharmaLearn" value={cost.per_certified_usd ?? 0} max={cost.manual_per_certified_usd ?? 1}
            display={money(cost.per_certified_usd)} caption="per learner" />
          <BarRow label="Manual build" value={cost.manual_per_certified_usd ?? 0} max={cost.manual_per_certified_usd ?? 1}
            display={money(cost.manual_per_certified_usd)} caption="per learner" tone="warning" />
          <p className="mt-4 border-t pt-4 text-sm text-stone-700">
            {money(cost.build_usd)} spent against {money(cost.manual_usd)} manual — <b>{money(cost.saved_usd)} saved</b> across the portfolio.
          </p>
        </ChartFrame>
      </div>

      <div className="mt-5 grid items-start gap-5 lg:grid-cols-2">
        <ChartFrame className="print-keep" title="Knowledge uplift"
          note={`Baseline and final scores from the ${uplift.learners} learner${uplift.learners === 1 ? "" : "s"} who sat both. One cohort measured twice, never two different groups.`}>
          <UpliftMeter baseline={uplift.baseline ?? 0} final={uplift.final ?? 0}
            label={`Pooled over every learner in the portfolio, not averaged over programmes — a mean of means would weight a pilot the same as a rollout.`} />
        </ChartFrame>

        {/* The differentiator, and the only block here that is not about speed or
            money: what never reached the field, and how often the experts agreed. */}
        <Card className="print-keep border-signal-100 bg-signal-50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base"><ScanLine size={17} className="text-signal-700" /> Caught before the field</CardTitle>
            <p className="mt-2 text-sm text-stone-600">
              Across the portfolio, checked against the source documents we hold.
            </p>
          </CardHeader>
          <CardContent className="space-y-2.5 text-sm">
            {[
              ["Findings raised by the checker", governance.findings],
              ["Publication-blocking defects", governance.blocking_found],
              ["Sent to a human reviewer", governance.raised_to_reviewers],
              ["Reviewer agreement", governance.agreement_percent === null ? "–" : `${governance.agreement_percent}% of ${governance.settled} settled`],
              ["Published with an override on record", governance.overrides],
              ["Citations checkable against stored sources", governance.coverage_percent === null ? "–" : `${governance.coverage_percent}%`],
            ].map(([label, value]) => (
              <div key={label as string} className="flex items-baseline justify-between gap-4 border-b border-signal-100 pb-2.5 last:border-0 last:pb-0">
                <span className="text-stone-700">{label as string}</span>
                <span className="shrink-0 font-semibold tabular-nums text-stone-900">{value as string | number}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card className="print-keep mt-5">
        <CardHeader>
          <CardTitle className="text-base">Programme by programme</CardTitle>
          <p className="mt-2 text-sm text-stone-600">Every row is a course that reached a cohort. Averages above are pooled from these learners, not from these rows.</p>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[42rem] text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wide text-stone-500">
                  <th className="py-2 pr-3 font-medium">Programme</th>
                  <th className="px-3 py-2 text-right font-medium">Certified</th>
                  <th className="px-3 py-2 text-right font-medium">Uplift</th>
                  <th className="px-3 py-2 text-right font-medium">Days to field</th>
                  <th className="px-3 py-2 text-right font-medium">Saved</th>
                  <th className="px-3 py-2 text-right font-medium">Findings</th>
                </tr>
              </thead>
              <tbody>
                {data.programmes.map((entry) => (
                  <tr key={entry.run_id} className="border-b last:border-0">
                    <td className="py-2.5 pr-3">
                      <Link href={`/courses/${entry.run_id}`} className="font-medium text-stone-800 hover:underline">{entry.drug}</Link>
                      <span className="ml-2 text-xs capitalize text-stone-600">{entry.state}</span>
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{entry.certified} / {entry.assigned}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{entry.average_uplift === null ? "–" : `+${entry.average_uplift}`}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{entry.days_to_publish ?? "–"}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{money(entry.cost_saved_usd)}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums">
                      {/* A cycle running already-approved content was not built or
                          checked again, and saying "0" would read as "nothing found". */}
                      {entry.findings === null
                        ? <span className="text-stone-500" title="Runs content built and checked for an earlier programme">reused</span>
                        : entry.findings}
                      {entry.overrides > 0 && <span className="text-warn-700"> · {entry.overrides} override</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <p className="mt-5 flex items-center gap-2 text-sm text-stone-600">
        <ShieldCheck size={15} className="text-stone-500" />
        Figures are measured from this workspace, not modelled. The manual baseline is stated, not observed —
        {" "}{speed.manual_days} days and {money(cost.manual_usd)} for the same work by hand.
      </p>
      <p className="mt-2 flex items-center gap-2 text-sm text-stone-600">
        <Users size={15} className="text-stone-500" />
        Archived programmes are included: they were delivered, and leaving them out would flatter the portfolio.
      </p>
    </AppShell>
  );
}
