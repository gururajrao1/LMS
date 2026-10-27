"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, ChevronUp, ExternalLink, FileText, Search, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { getJson, LibraryText } from "@/lib/api";

/**
 * The reference document itself, read beside the content rather than behind a link.
 *
 * We already hold these files — they are what the checker matches quotes against.
 * Serving them here closes the loop a reviewer otherwise has to close by hand:
 * the claim, the recorded quote, and now the document the quote came from, in the
 * page they were already on. It also means the evidence survives the far end
 * changing its URL, which for a label is not hypothetical.
 *
 * Rendered as paragraphs of the stored text, never as the source's own HTML: this
 * is untrusted third-party content and injecting it as markup would be a scripting
 * hole opened for the sake of typography.
 */

/** Split the flattened text into readable blocks without pretending to know its structure. */
function paragraphs(text: string): string[] {
  const out: string[] = [];
  const sentences = text.split(/(?<=[.:;])\s+/);
  let block = "";
  for (const sentence of sentences) {
    block += (block ? " " : "") + sentence;
    if (block.length > 420) { out.push(block); block = ""; }
  }
  if (block.trim()) out.push(block);
  return out;
}

function Marked({ text, query, from }: { text: string; query: string; from: number }) {
  if (!query.trim()) return <>{text}</>;
  const parts = text.split(new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "ig"));
  let hit = from;
  return (
    <>
      {parts.map((part, index) => {
        if (index % 2 === 0) return <span key={index}>{part}</span>;
        const position = hit++;
        return (
          <mark key={index} data-hit={position} className="rounded bg-warn-100 px-0.5 text-warn-900 [&[data-current=true]]:bg-warn-400">
            {part}
          </mark>
        );
      })}
    </>
  );
}

export function SourceSidecar({ runId, url, onClose, find = "" }: {
  runId: string;
  url: string;
  onClose: () => void;
  /** Text to jump to on open — the recorded quote behind a citation. */
  find?: string;
}) {
  // Held with the url it was fetched for, so switching documents shows "loading"
  // by comparison rather than by clearing state from inside an effect.
  const [loaded, setLoaded] = useState<{ url: string; value: LibraryText | null; error: string } | null>(null);
  const document_ = loaded?.url === url ? loaded.value : null;
  const error = loaded?.url === url ? loaded.error : "";
  // Long quotes rarely survive verbatim, so we search on a distinctive slice of
  // the opening rather than the whole sentence, which usually finds nothing.
  const [query, setQuery] = useState(find.split(/\s+/).slice(0, 6).join(" "));
  const [current, setCurrent] = useState(0);
  const body = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let live = true;
    getJson<LibraryText>(`/api/runs/${runId}/library/document?url=${encodeURIComponent(url)}`)
      .then((value) => { if (live) setLoaded({ url, value, error: "" }); })
      .catch(() => { if (live) setLoaded({ url, value: null, error: "This document is not held locally." }); });
    return () => { live = false; };
  }, [runId, url]);

  useEffect(() => {
    const root = window.document.documentElement;
    root.dataset.dockOpen = "true";
    return () => { delete root.dataset.dockOpen; };
  }, []);

  useEffect(() => {
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [onClose]);

  const blocks = useMemo(() => paragraphs(document_?.text ?? ""), [document_]);
  const counts = useMemo(() => {
    if (!query.trim() || !document_) return [] as number[];
    const pattern = new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "ig");
    return blocks.map((block) => (block.match(pattern) ?? []).length);
  }, [blocks, query, document_]);
  const total = counts.reduce((sum, value) => sum + value, 0);

  // Scrolling is a DOM effect on rendered marks, so it runs after paint rather
  // than being computed during render.
  useEffect(() => {
    if (!total) return;
    const marks = body.current?.querySelectorAll("mark");
    marks?.forEach((mark) => mark.removeAttribute("data-current"));
    const target = marks?.[Math.min(current, total - 1)];
    if (target) {
      target.setAttribute("data-current", "true");
      target.scrollIntoView({ block: "center", behavior: "smooth" });
    }
  }, [current, total, blocks]);

  const step = (delta: number) => setCurrent((value) => (total ? (value + delta + total) % total : 0));

  return (
    <aside aria-label={`Reference document: ${document_?.title ?? "loading"}`}
      className="fixed inset-y-0 right-0 z-50 flex w-[min(34rem,100vw)] flex-col border-l border-line bg-white shadow-2xl print:hidden">
      <div className="border-b p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-brand-700">
              <FileText size={14} /> Held here
            </p>
            <h2 className="mt-1 text-sm font-semibold leading-5">{document_?.title ?? "Loading…"}</h2>
          </div>
          <button type="button" onClick={onClose} aria-label="Close the document"
            className="-mr-1 shrink-0 rounded-lg p-1 text-stone-500 hover:bg-stone-100"><X size={16} /></button>
        </div>
        {document_ && (
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-stone-600">
            {document_.kind && <Badge variant="secondary">{document_.kind.replace(/_/g, " ")}</Badge>}
            <span className="tabular-nums">{document_.characters.toLocaleString()} characters</span>
            {document_.fetched_at && <span>· stored {document_.fetched_at.slice(0, 10)}</span>}
            <a href={document_.url} target="_blank" rel="noreferrer"
              className="inline-flex items-center gap-1 font-medium text-brand-700 hover:underline">
              original <ExternalLink size={11} />
            </a>
          </div>
        )}
        <div className="mt-3 flex items-center gap-2">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400" />
            <Input value={query} onChange={(event) => { setQuery(event.target.value); setCurrent(0); }}
              placeholder="Find in this document" className="h-9 pl-8 text-sm" />
          </div>
          <span className="w-16 shrink-0 text-right text-xs tabular-nums text-stone-600">
            {query.trim() ? (total ? `${Math.min(current + 1, total)} / ${total}` : "none") : ""}
          </span>
          <button type="button" onClick={() => step(-1)} disabled={!total} aria-label="Previous match"
            className="rounded-md border p-1.5 text-stone-600 disabled:opacity-40 hover:bg-stone-50"><ChevronUp size={14} /></button>
          <button type="button" onClick={() => step(1)} disabled={!total} aria-label="Next match"
            className="rounded-md border p-1.5 text-stone-600 disabled:opacity-40 hover:bg-stone-50"><ChevronDown size={14} /></button>
        </div>
        {find && !total && query.trim() && (
          <p className="mt-2 text-xs leading-5 text-warn-700">
            Not found in this document. The recorded quote may be paraphrased, or drawn from a different source.
          </p>
        )}
      </div>

      <div ref={body} className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-4">
        {error && <p className="text-sm text-danger-600">{error}</p>}
        {!document_ && !error && <p className="text-sm text-stone-500">Opening the stored document…</p>}
        {blocks.map((block, index) => (
          <p key={index} className="mb-3 text-sm leading-6 text-stone-700">
            <Marked text={block} query={query} from={counts.slice(0, index).reduce((sum, value) => sum + value, 0)} />
          </p>
        ))}
      </div>
    </aside>
  );
}
