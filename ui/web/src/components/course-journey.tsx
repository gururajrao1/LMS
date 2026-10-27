"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Check } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { getJson, Journey, JourneyStep } from "@/lib/api";

/**
 * The spine: the ten steps a programme goes through, in order, with the evidence
 * that each one happened.
 *
 * Everything here was already in the app, one step per tab, which reads as a pile
 * of features rather than a process. Laid out in sequence it answers the question a
 * client actually asks — what happens, in what order, and what is true at each
 * point — without anyone having to narrate it.
 */
const DOT: Record<JourneyStep["state"], string> = {
  done: "bg-brand-600 text-white",
  current: "border-2 border-brand-600 bg-white text-brand-700",
  waiting: "border border-line bg-white text-stone-400",
};

function Step({ step, index, last }: { step: JourneyStep; index: number; last: boolean }) {
  const waiting = step.state === "waiting";
  return (
    <li className="relative flex gap-4 pb-6 last:pb-0">
      {/* The rail is what makes it a sequence rather than a list. */}
      {!last && <span aria-hidden className={`absolute left-[15px] top-9 h-[calc(100%-1.5rem)] w-px ${
        step.state === "done" ? "bg-brand-200" : "bg-line"}`} />}
      <span className={`relative z-10 grid size-8 shrink-0 place-items-center rounded-full text-sm font-semibold tabular-nums ${DOT[step.state]}`}>
        {step.state === "done" ? <Check size={16} /> : index + 1}
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <Link href={step.href} className={`font-medium ${waiting ? "text-stone-500" : "text-stone-900 hover:underline"}`}>
            {step.title}
          </Link>
          {step.state === "current" && <Badge className="bg-brand-50 text-brand-700">In progress</Badge>}
        </div>
        <p className={`mt-1 text-sm leading-6 ${waiting ? "text-stone-500" : "text-stone-600"}`}>{step.detail}</p>
        {step.evidence.length > 0 && (
          <p className="mt-2 flex flex-wrap gap-x-2 gap-y-1 text-xs">
            {step.evidence.map((value, position) => (
              <span key={position} className="rounded-md bg-stone-100 px-2 py-0.5 font-medium tabular-nums text-stone-700">
                {value}
              </span>
            ))}
          </p>
        )}
      </div>
    </li>
  );
}

export function CourseJourney({ runId }: { runId: string }) {
  const [journey, setJourney] = useState<Journey | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getJson<Journey>(`/api/runs/${runId}/journey`).then(setJourney).catch(() => setError("Could not load the journey."));
  }, [runId]);

  if (!journey) return <Card><CardContent className="p-8 text-center text-stone-600">{error || "Reading the record…"}</CardContent></Card>;

  return (
    <Card>
      <CardContent className="p-6">
        <div className="flex flex-wrap items-end justify-between gap-4 border-b pb-5">
          <div>
            <h3 className="text-lg font-semibold tracking-tight">From a drug name to a certified field team</h3>
            <p className="mt-1.5 text-sm leading-6 text-stone-600">
              Every step below is read from the record, never stored — a step is done because the evidence for it
              exists, so this cannot run ahead of the work.
            </p>
          </div>
          <p className="text-right">
            <span className="block text-2xl font-semibold tabular-nums">{journey.done}<span className="text-stone-400">/{journey.total}</span></span>
            <span className="text-sm capitalize text-stone-600">{journey.state}</span>
          </p>
        </div>

        <ol className="mt-6">
          {journey.steps.map((step, index) => (
            <Step key={step.id} step={step} index={index} last={index === journey.steps.length - 1} />
          ))}
        </ol>

        <Link href="/portfolio" className="mt-2 inline-flex items-center gap-1.5 text-sm font-medium text-brand-700 hover:underline">
          See it consolidated across every programme <ArrowRight size={14} />
        </Link>
      </CardContent>
    </Card>
  );
}
