"use client";

import { FocusReader } from "@/components/focus-reader";

const SAMPLE = [
  "Ibrance (palbociclib) is a CDK4/6 inhibitor for HR-positive, HER2-negative advanced breast cancer.",
  "Dosing is once daily with food, 21 days on followed by 7 days off, in combination with endocrine therapy.",
  "Neutropenia is the most common adverse reaction: check blood counts before each cycle and at day 15 of the first two cycles.",
  "Reduce, interrupt, or discontinue for severe neutropenia or infections, per the label.",
];

export default function FocusExperimentPage() {
  return (
    <main className="mx-auto max-w-2xl p-6">
      <p className="text-xs font-semibold uppercase tracking-[.14em] text-stone-500">Experiment · Phase 1 prototype</p>
      <h1 className="mt-1 text-xl font-semibold text-ink">Focus-mode reading</h1>
      <p className="mt-2 text-sm leading-6 text-stone-600">
        One chunk at a time at full legibility, with position, free navigation,
        and a rereadable full-text view. Deliberately no blur: the evidence
        favors sequential disclosure. Nothing here affects the real training
        record — this page only tests the psychology.
      </p>
      <div className="mt-4">
        <FocusReader title="Ibrance essentials" chunks={SAMPLE} />
      </div>
    </main>
  );
}
