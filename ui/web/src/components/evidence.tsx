"use client";

import { useEffect, useState } from "react";
import { BookOpen, ExternalLink, Layers3, Quote, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { SourceSidecar } from "@/components/source-sidecar";
import { Citation, Evidence, getJson } from "@/lib/api";

/** A citation chip. Given a runId it opens the evidence behind the citation. */
export function CitationChip({ source, locator, onClick }: { source: string; locator: string; onClick?: () => void }) {
  const className = "inline-flex max-w-full items-center gap-1 rounded-md bg-brand-50 px-2 py-1 text-left text-xs font-medium text-brand-700";
  const label = <><span className="truncate">{source}</span><span className="shrink-0 opacity-60">· {locator}</span></>;
  if (!onClick) return <span className={className}>{label}</span>;
  return (
    <button type="button" onClick={onClick}
      className={`${className} transition-colors hover:bg-brand-100 focus-visible:ring-2 focus-visible:ring-brand-600 focus-visible:ring-offset-2 focus-visible:outline-none`}>
      {label}
    </button>
  );
}

function EvidencePanel({ runId, citation, onClose, onRead }: {
  runId: string; citation: Citation; onClose: () => void;
  /** Opens the stored document beside the page, jumped to the quote. */
  onRead?: (url: string, quote: string) => void;
}) {
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const query = new URLSearchParams({ title: citation.title ?? "", locator: citation.locator ?? "", url: citation.url ?? "" });
    let current = true;
    getJson<Evidence>(`/api/runs/${runId}/evidence?${query}`)
      .then((data) => { if (current) setEvidence(data); })
      .catch(() => { if (current) setError("This citation has no stored supporting text in the dossier."); });
    return () => { current = false; };
  }, [runId, citation]);

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[85vh] gap-0 overflow-y-auto sm:max-w-2xl">
        <DialogHeader className="pr-8">
          <p className="text-xs font-semibold uppercase tracking-[.14em] text-brand-700">Evidence</p>
          <DialogTitle className="text-lg leading-6">{evidence?.citation.title ?? citation.title ?? "Source"}</DialogTitle>
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <Badge variant="secondary">{evidence?.citation.locator || citation.locator}</Badge>
            {evidence && <Badge variant="outline">{evidence.claim.evidence_type}</Badge>}
          </div>
        </DialogHeader>

        {!evidence && !error && <p className="py-10 text-center text-stone-600">Retrieving the source text…</p>}
        {error && <p className="py-10 text-center text-stone-600">{error}</p>}

        {evidence && (
          <div className="mt-5 space-y-5">
            {evidence.citation.supporting_text && (
              <section>
                <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-stone-600">
                  <Quote size={13} /> What the source says
                </p>
                <blockquote className="mt-2 border-l-2 border-brand-600 bg-brand-50 py-3 pl-4 text-[15px] leading-7 text-stone-700">
                  {evidence.citation.supporting_text}
                </blockquote>
              </section>
            )}

            <section>
              <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-stone-600">
                <ShieldCheck size={13} /> The claim it supports
              </p>
              <p className="mt-2 leading-7 text-stone-700">{evidence.claim.text}</p>
              <p className="mt-2 text-xs text-stone-600">Collected in “{evidence.claim.section_title}”</p>
            </section>

            {evidence.related.length > 0 && (
              <section>
                <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-stone-600">
                  <Layers3 size={13} /> This source also supports {evidence.supports_claims - 1} other claim{evidence.supports_claims === 2 ? "" : "s"} in this course
                </p>
                <ul className="mt-2 space-y-2">
                  {evidence.related.map((claim) => (
                    <li key={claim.text} className="border-l-2 border-stone-200 pl-3 text-sm leading-6 text-stone-600">{claim.text}</li>
                  ))}
                </ul>
              </section>
            )}

            <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
              {/* The last step of the chain: claim, recorded quote, and now the
                  document the quote was taken from — without leaving the page or
                  depending on the publisher still serving that URL. */}
              {onRead && (
                <button type="button" onClick={() => onRead(evidence.citation.url, evidence.citation.supporting_text)}
                  className="inline-flex items-center gap-2 text-sm font-medium text-brand-700 hover:underline">
                  <BookOpen size={14} /> Read the stored document
                </button>
              )}
              {evidence.citation.url && (
                <a href={evidence.citation.url} target="_blank" rel="noreferrer"
                  className="inline-flex items-center gap-2 text-sm font-medium text-stone-600 hover:underline">
                  Open the authoritative source <ExternalLink size={14} />
                </a>
              )}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

/** Citation chips for one asset. Clicking a chip reveals the evidence behind it. */
export function Cites({ runId, citations }: { runId?: string; citations: Citation[] }) {
  const [open, setOpen] = useState<Citation | null>(null);
  const [reading, setReading] = useState<{ url: string; quote: string } | null>(null);
  if (!citations?.length) return null;
  return (
    <>
      <div className="mt-3 flex flex-wrap gap-2">
        {citations.map((citation, index) => (
          <CitationChip
            key={`${citation.source_id ?? citation.title}-${citation.locator}-${index}`}
            source={citation.source_id ?? citation.title ?? "Source"}
            locator={citation.locator}
            onClick={runId ? () => setOpen(citation) : undefined}
          />
        ))}
      </div>
      {runId && open && (
        <EvidencePanel runId={runId} citation={open} onClose={() => setOpen(null)}
          onRead={(url, quote) => { setReading({ url, quote }); setOpen(null); }} />
      )}
      {runId && reading && (
        <SourceSidecar runId={runId} url={reading.url} find={reading.quote} onClose={() => setReading(null)} />
      )}
    </>
  );
}
