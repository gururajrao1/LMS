"use client";

import { useState } from "react";
import { Maximize2 } from "lucide-react";
import { Cites } from "@/components/evidence";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Citation } from "@/lib/api";

export type Slide = { number: number; title: string; purpose: string; content?: string[]; citations?: Citation[] };

/** A 16:9 thumbnail that reads as a slide rather than a description of one. */
function Thumbnail({ slide, onOpen }: { slide: Slide; onOpen: () => void }) {
  return (
    <button type="button" onClick={onOpen}
      className="group flex flex-col overflow-hidden rounded-xl border bg-white text-left transition-shadow hover:shadow-md focus-visible:ring-2 focus-visible:ring-brand-600 focus-visible:ring-offset-2 focus-visible:outline-none">
      <div className="relative aspect-[16/9] w-full overflow-hidden border-b bg-white p-4">
        <div className="absolute inset-x-4 top-4 h-1 w-10 rounded-full bg-brand-600" />
        <p className="mt-4 line-clamp-2 text-[13px] font-semibold leading-5 text-ink">{slide.title}</p>
        <ul className="mt-2 space-y-1">
          {(slide.content ?? []).slice(0, 4).map((line, index) => (
            <li key={index} className="flex gap-1.5 text-[10px] leading-[14px] text-stone-600">
              <span className="mt-[5px] size-1 shrink-0 rounded-full bg-stone-400" />
              <span className="line-clamp-2">{line}</span>
            </li>
          ))}
        </ul>
        <span className="absolute bottom-3 right-4 text-[10px] font-medium tabular-nums text-stone-400">{slide.number}</span>
        <span className="absolute inset-0 grid place-items-center bg-surface-deep/0 opacity-0 transition-all group-hover:bg-surface-deep/5 group-hover:opacity-100">
          <span className="rounded-lg bg-white px-2.5 py-1.5 text-xs font-medium shadow-sm"><Maximize2 size={13} className="mr-1 inline" />Open slide</span>
        </span>
      </div>
      <div className="p-3">
        <p className="text-xs text-stone-600">{slide.purpose}</p>
      </div>
    </button>
  );
}

export function DeckGrid({ slides, runId }: { slides: Slide[]; runId: string }) {
  const [open, setOpen] = useState<Slide | null>(null);
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {slides.map((slide) => <Thumbnail key={slide.number} slide={slide} onOpen={() => setOpen(slide)} />)}
      </div>
      {open && (
        <Dialog open onOpenChange={(value) => !value && setOpen(null)}>
          <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-3xl">
            <DialogHeader className="pr-8">
              <p className="text-xs font-semibold uppercase tracking-[.14em] text-brand-700">Slide {open.number}</p>
              <DialogTitle className="text-xl leading-7">{open.title}</DialogTitle>
            </DialogHeader>
            <div className="mt-4 rounded-xl border bg-white p-6">
              <ul className="space-y-3">
                {(open.content ?? []).map((line, index) => (
                  <li key={index} className="flex gap-3 leading-7 text-stone-700">
                    <span className="mt-[11px] size-1.5 shrink-0 rounded-full bg-brand-600" />
                    <span>{line}</span>
                  </li>
                ))}
              </ul>
              {!open.content?.length && <p className="text-stone-600">This slide has no body copy in the deck specification.</p>}
            </div>
            <p className="mt-4 text-sm text-stone-600"><b>Why this slide is here:</b> {open.purpose}</p>
            {open.citations && <Cites runId={runId} citations={open.citations} />}
          </DialogContent>
        </Dialog>
      )}
    </>
  );
}
