"use client";

import { useState } from "react";

/** Focus-mode reading experiment, revised: sequential disclosure, no occlusion.
 *
 * Evidence (Snell 2024 on Bionic-style highlighting, Benedetto 2015 on RSVP)
 * finds no comprehension benefit in blurring or rapidly flashing the rest of
 * the text while suppressing regressions. So this reader shows one chunk at a
 * time at full legibility, with position, free navigation, and a rereadable
 * full-text view instead of blur.
 */
export function FocusReader({ chunks, title }: { chunks: string[]; title?: string }) {
  const [active, setActive] = useState(0);
  const [showAll, setShowAll] = useState(false);
  const total = chunks.length;
  if (total === 0) return <p className="text-sm text-stone-600">Nothing to read yet.</p>;
  const current = Math.min(active, total - 1);
  return (
    <div>
      {title && <h3 className="text-base font-semibold text-ink">{title}</h3>}
      <p className="mt-1 text-xs text-stone-500" aria-live="polite">
        Chunk {current + 1} of {total}{showAll ? " · full text" : ""}
      </p>
      {showAll ? (
        <ol className="mt-3 space-y-2">
          {chunks.map((chunk, index) => (
            <li key={index}
              className={`rounded-xl border p-3 text-sm leading-6 ${index === current ? "border-brand-600 bg-white text-ink" : "border-stone-200 bg-surface text-stone-700"}`}>
              <span className="mr-2 text-xs font-medium tabular-nums text-stone-400">{index + 1}</span>{chunk}
            </li>
          ))}
        </ol>
      ) : (
        <div className="mt-3 rounded-xl border border-brand-600 bg-white p-4">
          <p className="text-sm leading-7 text-ink">{chunks[current]}</p>
        </div>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button type="button" disabled={current === 0} onClick={() => { setActive(current - 1); setShowAll(false); }}
          className="rounded-lg border px-3 py-1.5 text-sm font-medium disabled:opacity-40">Previous</button>
        <button type="button" disabled={current === total - 1} onClick={() => { setActive(current + 1); setShowAll(false); }}
          className="rounded-lg border px-3 py-1.5 text-sm font-medium disabled:opacity-40">Next</button>
        <button type="button" onClick={() => setShowAll((value) => !value)} aria-expanded={showAll}
          className="rounded-lg border px-3 py-1.5 text-sm font-medium">
          {showAll ? "Focus one chunk" : "Show all (reread)"}
        </button>
      </div>
    </div>
  );
}
