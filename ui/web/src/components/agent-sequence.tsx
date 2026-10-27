"use client";

import { useEffect, useRef } from "react";

/**
 * The agent run drawn as a UML sequence diagram rather than a list of steps.
 *
 * A log of forty-four lines says the work happened; it does not say who did it or
 * that anything checked anything. The point of this run is the maker-checker seam
 * — research gathers evidence, an author writes from it, a checker verifies every
 * citation against the stored sources — and a diagram is the only shape that shows
 * a handoff. Solid arrows dispatch work, dashed arrows return it, and the checker
 * keeps the indigo the rest of the product reserves for automated review.
 *
 * Stages map to lanes rather than each carrying their own routing, so the agent
 * stays free to add a stage without the diagram needing to be told about it.
 */

type Lane = "agent" | "research" | "author" | "checker";

const LANES: { id: Lane; label: string; blurb: string; x: number }[] = [
  { id: "agent", label: "Agent", blurb: "orchestrates", x: 11 },
  { id: "research", label: "Research", blurb: "gathers evidence", x: 37 },
  { id: "author", label: "Author", blurb: "writes assets", x: 63 },
  { id: "checker", label: "Checker", blurb: "verifies citations", x: 89 },
];

const X = Object.fromEntries(LANES.map((lane) => [lane.id, lane.x])) as Record<Lane, number>;

type Message = { from: Lane; to: Lane; returns: boolean };

/** Which lanes a stage runs between. Unknown stages sit on the agent's own lane. */
function route(stage: string): Message {
  if (stage.startsWith("research_")) return { from: "agent", to: "research", returns: false };
  if (stage === "collate_evidence") return { from: "research", to: "agent", returns: true };
  if (stage.startsWith("generate_")) return { from: "agent", to: "author", returns: false };
  if (stage.startsWith("render_")) return { from: "author", to: "agent", returns: true };
  if (stage === "verify_citations") return { from: "agent", to: "checker", returns: false };
  if (stage.startsWith("verify_")) return { from: "checker", to: "agent", returns: true };
  return { from: "agent", to: "agent", returns: false };
}

export type SequenceStep = { stage: string; message: string; status: string };

const ROW = 54;

/** Marks the lane currently being waited on, so the diagram has a live edge. */
function Pulse({ lane }: { lane: Lane }) {
  return (
    <span aria-hidden className="absolute size-2 animate-pulse rounded-full bg-brand-600"
      style={{ left: `calc(${X[lane]}% - 4px)`, top: 36 }} />
  );
}

function Row({ step, active }: { step: SequenceStep; active: boolean }) {
  const { from, to, returns } = route(step.stage);
  const failed = step.status === "failed";
  const checker = from === "checker" || to === "checker";
  const line = failed ? "bg-danger-500" : checker ? "bg-signal-600" : "bg-stone-400";
  const dash = failed ? "text-danger-500" : checker ? "text-signal-600" : "text-stone-400";
  const head = failed ? "border-l-danger-500" : checker ? "border-l-signal-600" : "border-l-stone-400";

  // A self-message is its own shape in UML: out, down, and back to the same lane.
  if (from === to) {
    return (
      <li className="relative motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-top-1" style={{ height: ROW }}>
        <span className="absolute whitespace-nowrap text-xs font-medium text-ink"
          style={{ left: `calc(${X[from]}% + 4.5rem)`, top: 10 }}>
          {step.message}
        </span>
        <span className={`absolute rounded-r-md border-y border-r ${failed ? "border-danger-500" : "border-stone-400"}`}
          style={{ left: `${X[from]}%`, top: 28, width: "4rem", height: 16 }} />
        <span className={`absolute size-0 border-y-[5px] border-l-[7px] border-y-transparent ${head} rotate-180`}
          style={{ left: `${X[from]}%`, top: 39 }} />
        {active && <Pulse lane={from} />}
      </li>
    );
  }

  const left = Math.min(X[from], X[to]);
  const width = Math.abs(X[to] - X[from]);
  const rightwards = X[to] > X[from];

  return (
    <li className="relative motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-top-1" style={{ height: ROW }}>
      <span
        className={`absolute line-clamp-2 -translate-x-1/2 text-center text-xs leading-4 ${failed ? "text-danger-700" : "text-ink"} ${returns ? "font-normal" : "font-medium"}`}
        style={{ left: `${left + width / 2}%`, top: 4, maxWidth: "17rem", width: "max-content" }}
      >
        {step.message}
      </span>
      {/* Dashed on the way back, as UML draws a reply. The dash inherits its colour
          from the element rather than a theme variable, so it cannot silently fall
          back to transparent if a palette name changes. */}
      <span
        className={`absolute h-px ${returns ? dash : line}`}
        style={{
          left: `${left}%`,
          width: `${width}%`,
          top: 40,
          ...(returns
            ? {
                backgroundImage: "linear-gradient(to right, currentColor 58%, transparent 58%)",
                backgroundSize: "7px 1px",
                backgroundRepeat: "repeat-x",
              }
            : {}),
        }}
      />
      <span
        className={`absolute size-0 border-y-[5px] border-l-[7px] border-y-transparent ${head} ${rightwards ? "" : "rotate-180"}`}
        style={{ left: rightwards ? `calc(${left + width}% - 6px)` : `${left}%`, top: 35 }}
      />
      {active && <Pulse lane={to} />}
    </li>
  );
}

export function AgentSequence({ steps, running }: { steps: SequenceStep[]; running: boolean }) {
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [steps.length]);

  return (
    // Scrolls as one unit so the lifelines stay under their actors on a narrow screen.
    <div className="overflow-x-auto">
      <div className="relative h-16 min-w-[42rem] border-b bg-stone-50">
        {LANES.map((lane) => (
          <div key={lane.id}
            className={`absolute w-28 -translate-x-1/2 rounded-lg border px-2 py-1.5 text-center ${lane.id === "checker" ? "border-signal-600/40 bg-signal-50" : "border-stone-300 bg-white"}`}
            style={{ left: `${lane.x}%`, top: 10 }}>
            <p className={`text-sm font-semibold leading-4 ${lane.id === "checker" ? "text-signal-700" : "text-ink"}`}>{lane.label}</p>
            <p className="text-[10px] leading-3 text-stone-500">{lane.blurb}</p>
          </div>
        ))}
      </div>

      <div ref={scroller} role="log" aria-live="polite" className="relative h-[420px] overflow-y-auto overscroll-contain">
        <div className="relative min-h-full min-w-[42rem] py-3">
          {LANES.map((lane) => (
            <span key={lane.id} aria-hidden
              className={`absolute top-0 bottom-0 w-px ${lane.id === "checker" ? "bg-signal-600/25" : "bg-stone-300"}`}
              style={{ left: `${lane.x}%` }} />
          ))}
          <ol className="relative">
            {steps.map((step, index) => (
              <Row key={step.stage} step={step} active={running && index === steps.length - 1} />
            ))}
          </ol>
          {!steps.length && (
            <p className="relative py-16 text-center text-sm text-stone-600">Connecting to the agent log…</p>
          )}
        </div>
      </div>
    </div>
  );
}
