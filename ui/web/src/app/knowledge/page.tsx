"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { CircleAlert, Database, ExternalLink, FileUp, Globe, Inbox, Layers3, Link2, Search, TriangleAlert, Upload } from "lucide-react";
import { AppShell, Cites, Loading, Stat } from "@/components/app-shell";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getJson, Knowledge, sendForm, sendJson, StagedSource } from "@/lib/api";
import { useSession } from "@/lib/session";

type Course = { id: string; run_id?: string; name: string; generic: string };

function bytes(value?: number) {
  if (!value) return "";
  return value > 1_048_576 ? `${(value / 1_048_576).toFixed(1)} MB` : `${Math.max(1, Math.round(value / 1024))} KB`;
}

export default function KnowledgeHub() {
  const user = useSession(["admin", "reviewer"]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [runId, setRunId] = useState("");
  const [loaded, setLoaded] = useState<{ runId: string; data: Knowledge } | null>(null);
  const [query, setQuery] = useState("");
  const [staged, setStaged] = useState<StagedSource[]>([]);
  const [url, setUrl] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getJson<Course[]>("/api/courses").then((all) => {
      const ready = all.filter((course) => course.run_id);
      setCourses(ready);
      setRunId((current) => current || ready[0]?.run_id || "");
    }).catch(() => setError("Start the API on port 8000 to browse the data store."));
    getJson<StagedSource[]>("/api/uploads").then(setStaged).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!runId) return;
    let current = true;
    getJson<Knowledge>(`/api/runs/${runId}/knowledge`)
      .then((data) => { if (current) setLoaded({ runId, data }); })
      .catch(() => { if (current) setError("This run has no stored dossier."); });
    return () => { current = false; };
  }, [runId]);

  const knowledge = loaded?.runId === runId ? loaded.data : null;
  const sections = useMemo(() => {
    if (!knowledge) return [];
    const needle = query.trim().toLowerCase();
    if (!needle) return knowledge.sections;
    return knowledge.sections
      .map((section) => ({ ...section, claims: section.claims.filter((claim) => claim.text.toLowerCase().includes(needle)) }))
      .filter((section) => section.claims.length || section.title.toLowerCase().includes(needle));
  }, [knowledge, query]);

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const input = form.elements.namedItem("document") as HTMLInputElement;
    if (!input.files?.length) return;
    setBusy(true); setError("");
    try {
      const body = new FormData();
      body.append("file", input.files[0]);
      body.append("note", note);
      const record = await sendForm<StagedSource>("/api/uploads", body);
      setStaged((current) => [record, ...current]);
      form.reset(); setNote("");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Upload failed"); }
    finally { setBusy(false); }
  }

  async function pull(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError("");
    try {
      const record = await sendJson<StagedSource>("/api/uploads/web", { url, note });
      setStaged((current) => [record, ...current]);
      setUrl(""); setNote("");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not pull that URL"); }
    finally { setBusy(false); }
  }

  if (!user) return <AppShell><Loading /></AppShell>;
  const claimCount = knowledge?.sections.reduce((total, section) => total + section.claims.length, 0) ?? 0;

  return (
    <AppShell user={user}>
      <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
        <div>
          <p className="text-sm font-semibold text-brand-700">DATA STORE</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">Knowledge hub</h1>
          <p className="mt-2 text-stone-600">Every claim the agent collected, the source behind it, and the documents staged for the next run.</p>
        </div>
        {courses.length > 1 && (
          <div className="w-full sm:w-64">
            <label htmlFor="knowledge-course" className="text-sm font-medium">Course</label>
            <NativeSelect id="knowledge-course" value={runId} onChange={(event) => setRunId(event.target.value)} className="mt-2 h-9">
              {courses.map((course) => <option key={course.run_id} value={course.run_id}>{course.name}</option>)}
            </NativeSelect>
          </div>
        )}
      </div>

      {error && <p className="mt-5 text-sm text-danger-600">{error}</p>}

      <section className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat icon={Layers3} value={knowledge?.sections.length ?? "–"} label="Research sections" tone="brand" />
        <Stat icon={Database} value={claimCount || "–"} label="Normalized claims" />
        <Stat icon={Link2} value={knowledge?.sources.length ?? "–"} label="Authoritative sources" />
        <Stat icon={Inbox} value={staged.length} label="Staged documents" tone="warn" />
      </section>

      <Tabs defaultValue="dossier" className="mt-7">
        <TabsList className="h-auto flex-wrap bg-white p-1 shadow-sm">
          <TabsTrigger value="dossier"><Database /> Dossier</TabsTrigger>
          <TabsTrigger value="sources"><Link2 /> Sources</TabsTrigger>
          <TabsTrigger value="ingest"><Upload /> Add sources</TabsTrigger>
        </TabsList>

        <TabsContent value="dossier" className="mt-5">
          {!knowledge ? <Loading label="Loading the dossier…" /> : (
            <div className="space-y-5">
              <div className="relative">
                <Search size={16} className="absolute top-1/2 left-3 -translate-y-1/2 text-stone-500" />
                <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search every collected claim…" className="h-10 pl-9" />
              </div>

              {(knowledge.gaps.length > 0 || knowledge.warnings.length > 0) && (
                <div className="grid gap-4 md:grid-cols-2">
                  {knowledge.gaps.length > 0 && (
                    <Card><CardHeader><CardTitle className="flex items-center gap-2 text-base"><CircleAlert size={16} className="text-warn-600" /> Recorded gaps</CardTitle></CardHeader>
                      <CardContent><ul className="space-y-2 text-sm leading-6 text-stone-600">{knowledge.gaps.map((gap) => <li key={gap}>• {gap}</li>)}</ul></CardContent></Card>
                  )}
                  {knowledge.warnings.length > 0 && (
                    <Card><CardHeader><CardTitle className="flex items-center gap-2 text-base"><TriangleAlert size={16} className="text-warn-600" /> Warnings</CardTitle></CardHeader>
                      <CardContent><ul className="space-y-2 text-sm leading-6 text-stone-600">{knowledge.warnings.map((warning) => <li key={warning}>• {warning}</li>)}</ul></CardContent></Card>
                  )}
                </div>
              )}

              <Card>
                <CardHeader><CardTitle>{knowledge.title}</CardTitle><p className="mt-2 text-sm text-stone-600">{sections.length} section(s){query ? ` matching “${query}”` : ""}</p></CardHeader>
                <CardContent>
                  <Accordion>
                    {sections.map((section) => (
                      <AccordionItem key={section.id} value={section.id}>
                        <AccordionTrigger>
                          <span className="flex flex-1 items-center justify-between gap-3 pr-3 text-left">
                            <span>{section.title}</span>
                            <Badge variant="secondary" className="shrink-0">{section.claims.length}</Badge>
                          </span>
                        </AccordionTrigger>
                        <AccordionContent>
                          {section.summary && <p className="mb-4 leading-7 text-stone-600">{section.summary}</p>}
                          <div className="space-y-3">
                            {section.claims.map((claim, index) => (
                              <div key={`${section.id}-${index}`} className="rounded-xl border bg-stone-50 p-4">
                                <p className="leading-7 text-stone-700">{claim.text}</p>
                                <p className="mt-2 text-xs uppercase tracking-wide text-stone-500">{claim.evidence_type}</p>
                                <Cites runId={runId} citations={claim.citations} />
                              </div>
                            ))}
                          </div>
                        </AccordionContent>
                      </AccordionItem>
                    ))}
                  </Accordion>
                  {!sections.length && <p className="py-8 text-center text-stone-600">No claims match that search.</p>}
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>

        <TabsContent value="sources" className="mt-5">
          <div className="grid gap-4 md:grid-cols-2">
            {(knowledge?.sources ?? []).map((source) => (
              <Card key={source.source_id ?? source.url}>
                <CardHeader>{source.source_id && <Badge variant="secondary" className="w-fit">{source.source_id}</Badge>}<CardTitle className="pt-2 text-base leading-6">{source.title}</CardTitle></CardHeader>
                <CardContent>
                  {source.publisher && <p className="text-sm text-stone-600">{source.publisher}{source.version ? ` · ${source.version}` : ""}</p>}
                  <a className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-brand-700 hover:underline" href={source.url} target="_blank" rel="noreferrer">Open authoritative source <ExternalLink size={14} /></a>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="ingest" className="mt-5">
          <div className="grid gap-5 lg:grid-cols-2">
            <Card>
              <CardHeader><CardTitle className="flex items-center gap-2 text-base"><FileUp size={17} className="text-brand-700" /> Upload a document</CardTitle><p className="mt-2 text-sm text-stone-600">Label documents, congress decks or internal guidance for the medical team.</p></CardHeader>
              <CardContent>
                <form onSubmit={upload} className="space-y-4">
                  <input type="file" name="document" required className="block w-full text-sm text-stone-600 file:mr-3 file:rounded-lg file:border-0 file:bg-brand-50 file:px-3 file:py-2 file:text-sm file:font-medium file:text-brand-700" />
                  <Input value={note} onChange={(event) => setNote(event.target.value)} placeholder="Note (what is this and why)" />
                  <Button type="submit" disabled={busy} className="bg-brand-600 hover:bg-brand-800"><Upload /> Stage document</Button>
                </form>
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Globe size={17} className="text-brand-700" /> Pull from the web</CardTitle><p className="mt-2 text-sm text-stone-600">Fetch a page now and keep a copy with its retrieval date.</p></CardHeader>
              <CardContent>
                <form onSubmit={pull} className="space-y-4">
                  <Input value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://www.accessdata.fda.gov/…" required />
                  <Input value={note} onChange={(event) => setNote(event.target.value)} placeholder="Note (optional)" />
                  <Button type="submit" disabled={busy || !url.trim()} className="bg-brand-600 hover:bg-brand-800"><Globe /> Fetch and stage</Button>
                </form>
              </CardContent>
            </Card>
          </div>

          <Card className="mt-5">
            <CardHeader><CardTitle className="text-base">Staged sources ({staged.length})</CardTitle><p className="mt-2 text-sm text-stone-600">Held in the data store for the medical team. The bundled Ibrance demo run uses its own fixed source set.</p></CardHeader>
            <CardContent className="space-y-3">
              {staged.map((entry) => (
                <div key={entry.id} className="flex flex-wrap items-start justify-between gap-3 rounded-xl border p-4">
                  <div className="min-w-0">
                    <p className="flex items-center gap-2 font-medium">
                      {entry.kind === "web" ? <Globe size={15} className="shrink-0 text-stone-500" /> : <FileUp size={15} className="shrink-0 text-stone-500" />}
                      <span className="truncate">{entry.title || entry.name}</span>
                    </p>
                    {entry.kind === "web" && <p className="mt-1 truncate text-xs text-stone-600">{entry.name}</p>}
                    {entry.note && <p className="mt-2 text-sm leading-6 text-stone-600">{entry.note}</p>}
                    <p className="mt-2 text-xs text-stone-500">{new Date(entry.added_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}{entry.bytes ? ` · ${bytes(entry.bytes)}` : ""}</p>
                  </div>
                  <Badge className={entry.status === "staged" ? "bg-brand-50 text-brand-700" : "bg-warn-50 text-warn-700"}>
                    {entry.status === "staged" ? "Staged" : "Unreachable"}
                  </Badge>
                </div>
              ))}
              {!staged.length && <p className="py-6 text-center text-stone-600">Nothing staged yet.</p>}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </AppShell>
  );
}
