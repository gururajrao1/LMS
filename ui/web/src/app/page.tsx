"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, CheckCircle2, FileText, Presentation, Video } from "lucide-react";
import { Brand, ROLE_LABEL } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { getJson, Person, RoleEntry, sendJson } from "@/lib/api";
import { homeFor, writeSession } from "@/lib/session";

const BUILTIN_BLURBS: Record<string, string> = {
  admin: "Create courses, publish and schedule training",
  reviewer: "Review content and sign it off",
  msl: "Field medical training track",
  hcp: "Clinical training track",
};

export default function Login() {
  const router = useRouter();
  const [people, setPeople] = useState<Person[]>([]);
  const [entries, setEntries] = useState<RoleEntry[]>([]);
  const [role, setRole] = useState("admin");
  const [userId, setUserId] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    getJson<Person[]>("/api/people").then(setPeople).catch(() => setError("Start the API on port 8000 to sign in."));
    getJson<RoleEntry[]>("/api/roles").then(setEntries).catch(() => undefined);
  }, []);

  const matching = people.filter((person) => person.role === role);
  const tabs = entries.length ? entries : ["admin", "reviewer", "msl", "hcp"].map((id) => ({ id, label: ROLE_LABEL[id] ?? id, description: BUILTIN_BLURBS[id] ?? "" }));
  const selected = matching.find((person) => person.id === userId) ?? matching[0];

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    try {
      const person = await sendJson<Person>("/api/session", { user_id: selected.id });
      writeSession(person);
      router.push(homeFor(person));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not sign in"); }
  }

  return (
    <main className="grid min-h-screen lg:grid-cols-2">
      {/* Deepest surface, not the slab green: over a full half-screen the mid step
          flattens out, and white type needs the extra depth behind it. */}
      <section className="relative hidden overflow-hidden bg-surface-deeper p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="absolute inset-0 opacity-25 [background-image:radial-gradient(circle_at_15%_10%,var(--color-brand-500),transparent_45%),radial-gradient(circle_at_85%_75%,var(--color-signal-600),transparent_40%)]" />
        <div className="relative"><Brand dark /></div>
        <div className="relative max-w-xl">
          <p className="mb-5 text-sm font-semibold uppercase tracking-[.18em] text-brand-400">Medical learning, built with evidence</p>
          <h1 className="text-5xl font-semibold leading-[1.08] tracking-tight">Turn trusted sources into field-ready training.</h1>
          <div className="mt-10 grid grid-cols-3 gap-3 text-sm">
            {[[Presentation, "PPTX"], [Video, "Storyboard"], [FileText, "FAQ + Quiz"]].map(([Icon, label]) => {
              const AssetIcon = Icon as typeof Presentation;
              return <div key={label as string} className="rounded-xl border border-white/15 bg-white/8 p-4"><AssetIcon className="mb-3 text-brand-300" size={22} />{label as string}</div>;
            })}
          </div>
        </div>
        <p className="relative flex items-center gap-2 text-sm text-stone-300"><CheckCircle2 size={16} /> Every learning claim remains traceable.</p>
      </section>

      <section className="flex items-center justify-center bg-white dark:bg-surface px-6 py-12">
        <form onSubmit={submit} className="w-full max-w-md">
          <div className="mb-10 lg:hidden"><Brand /></div>
          <p className="text-sm font-semibold text-brand-700 dark:text-brand-300">Welcome back</p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight">Sign in to PharmaLearn</h2>
          <p className="mt-2 text-sm leading-6 text-stone-600 dark:text-muted-foreground">Choose a role, then the person you want to sign in as.</p>

          <div className="mt-7 grid grid-cols-2 gap-2">
            {tabs.map((entry) => (
              <button key={entry.id} type="button" aria-pressed={role === entry.id} onClick={() => { setRole(entry.id); setUserId(""); }}
                className={`rounded-xl border p-3 text-left transition-colors ${role === entry.id ? "border-brand-600 bg-brand-50 dark:bg-brand-950" : "hover:bg-stone-50 dark:hover:bg-surface-sunk"}`}>
                <p className="text-sm font-semibold">{entry.label}</p>
                <p className="mt-1 text-xs leading-5 text-stone-600 dark:text-muted-foreground">{entry.description}</p>
              </button>
            ))}
          </div>

          <div className="mt-5 space-y-2">
            {matching.map((person) => (
              <button key={person.id} type="button" aria-pressed={selected?.id === person.id} onClick={() => setUserId(person.id)}
                className={`flex w-full items-center justify-between gap-3 rounded-xl border p-3 text-left transition-colors ${selected?.id === person.id ? "border-brand-600 bg-brand-50 dark:bg-brand-950" : "hover:bg-stone-50 dark:hover:bg-surface-sunk"}`}>
                <span>
                  <span className="block text-sm font-medium">{person.name}</span>
                  <span className="block text-xs text-stone-600 dark:text-muted-foreground">{person.title}</span>
                </span>
                {selected?.id === person.id && <CheckCircle2 size={17} className="shrink-0 text-brand-700 dark:text-brand-300" />}
              </button>
            ))}
            {!matching.length && !error && <p className="text-sm text-stone-600 dark:text-muted-foreground">Loading the demo roster…</p>}
          </div>

          {error && <p className="mt-5 text-sm text-danger-600 dark:text-danger-300">{error}</p>}
          <Button type="submit" disabled={!selected} className="mt-7 h-11 w-full bg-brand-600 hover:bg-brand-800">Sign in{selected ? ` as ${selected.name}` : ""} <ArrowRight /></Button>
          <p className="mt-6 text-center text-xs text-stone-500 dark:text-stone-400">For authorized medical education use</p>
        </form>
      </section>
    </main>
  );
}
