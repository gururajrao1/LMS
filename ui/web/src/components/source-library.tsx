"use client";

import { useEffect, useState } from "react";
import { BookOpen, ExternalLink, FileText, Link2 } from "lucide-react";
import { SourceSidecar } from "@/components/source-sidecar";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getJson, Library } from "@/lib/api";

/**
 * Every source this course cites, split by whether the document is here.
 *
 * The distinction is the point. "Sources" on a course means links we recorded;
 * "held" is the stronger claim — the file is on disk, it is what the checker
 * matched quotes against, and it can be read without leaving the app or trusting
 * that the publisher still serves that URL.
 */
export function SourceLibrary({ runId }: { runId: string }) {
  const [library, setLibrary] = useState<Library | null>(null);
  const [reading, setReading] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);

  useEffect(() => { getJson<Library>(`/api/runs/${runId}/library`).then(setLibrary).catch(() => setLibrary(null)); }, [runId]);

  if (!library) return <Card><CardContent className="p-8 text-center text-stone-600">Loading the reference library…</CardContent></Card>;

  const held = library.documents.filter((entry) => entry.held);
  const linked = library.documents.filter((entry) => !entry.held);
  const visible = showAll ? linked : linked.slice(0, 8);

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Reference library</CardTitle>
          <p className="mt-2 text-sm leading-6 text-stone-600">
            <b>{library.held}</b> of {library.total} cited documents are stored here in full and can be read in
            the app. Those are the ones the checker matches recorded quotes against — a citation to a document
            we hold is verifiable; the rest are links we can only follow.
          </p>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 md:grid-cols-2">
            {held.map((entry) => (
              <button key={entry.key} type="button" onClick={() => setReading(entry.url)}
                className="flex h-full flex-col rounded-xl border p-4 text-left transition-colors hover:border-brand-600 hover:bg-brand-50">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm font-medium leading-5">{entry.title}</p>
                  <FileText size={15} className="mt-0.5 shrink-0 text-brand-700" />
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-stone-600">
                  {entry.kind && <Badge variant="secondary">{entry.kind.replace(/_/g, " ")}</Badge>}
                  {entry.fetched_at && <span>stored {entry.fetched_at.slice(0, 10)}</span>}
                  {/* One document cited under several URL spellings is still one
                      document; saying so is more honest than counting it twice. */}
                  {entry.listed_as > 1 && <span>· cited under {entry.listed_as} URLs</span>}
                  {!entry.cited && <span>· fetched to resolve a citation</span>}
                </div>
                <p className="mt-3 flex items-center gap-1.5 text-xs font-medium text-brand-700">
                  <BookOpen size={13} /> Read it here
                </p>
              </button>
            ))}
          </div>

          {linked.length > 0 && (
            <div className="mt-7">
              <h3 className="text-sm font-semibold">Linked, not stored <span className="font-normal text-stone-500">({linked.length})</span></h3>
              <p className="mt-1 text-sm text-stone-600">
                Recorded as sources but not held as files, so a quote against them cannot be machine-verified.
              </p>
              <div className="mt-3 space-y-1.5">
                {visible.map((entry) => (
                  <a key={entry.key} href={entry.url} target="_blank" rel="noreferrer"
                    className="flex items-start gap-2 rounded-lg px-2 py-1.5 text-sm leading-5 text-stone-700 hover:bg-stone-50">
                    <Link2 size={14} className="mt-0.5 shrink-0 text-stone-400" />
                    <span className="min-w-0 flex-1">{entry.title || entry.url}</span>
                    <ExternalLink size={12} className="mt-1 shrink-0 text-stone-400" />
                  </a>
                ))}
              </div>
              {linked.length > 8 && (
                <button type="button" onClick={() => setShowAll((value) => !value)}
                  className="mt-3 text-sm font-medium text-brand-700 hover:underline">
                  {showAll ? "Show fewer" : `Show all ${linked.length}`}
                </button>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {reading && <SourceSidecar runId={runId} url={reading} onClose={() => setReading(null)} />}
    </>
  );
}
