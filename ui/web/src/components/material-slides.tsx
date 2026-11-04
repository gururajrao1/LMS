"use client";

import { useMemo, useState } from "react";
import { Presentation } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { API } from "@/lib/api";

/** Turn pasted training text into a downloadable .pptx deck. */
export function MaterialSlidesPanel() {
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const slideCount = useMemo(() => {
    const blocks = text.split(/\n\s*\n/).map((block) => block.trim()).filter(Boolean);
    return Math.min(blocks.length + (text.trim() ? 1 : 0), 31);
  }, [text]);

  async function download() {
    setBusy(true); setError("");
    try {
      const response = await fetch(`${API}/api/presentations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, text }),
      });
      if (!response.ok) throw new Error(response.status === 400 ? "Add some text first — blank lines split slides." : "Could not build the deck");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${(title.trim() || "training").replace(/[^\w-]+/g, "-").slice(0, 60)}.pptx`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not build the deck"); }
    finally { setBusy(false); }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base"><Presentation size={17} className="text-brand-700" /> Training slides (.pptx)</CardTitle>
        <p className="mt-2 text-sm text-stone-600">
          Paste the present text — each block separated by a blank line becomes one slide.
          The first line is the heading, the rest become bullets.
          {text.trim() ? ` About ${slideCount} slide${slideCount === 1 ? "" : "s"} including the title slide.` : ""}
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && <p className="text-sm text-danger-600">{error}</p>}
        <Input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Deck title (e.g. Ibrance nurse training)" />
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          rows={10}
          placeholder={"Dosing\n- 125 mg once daily for 21 days\n- Take with food\n\nSafety\n- Neutropenia: hold and monitor\n- Counsel on infection signs"}
          className="w-full rounded-xl border border-stone-200 bg-white p-3 font-mono text-sm leading-6 text-stone-700 placeholder:text-stone-400 focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
        <Button disabled={busy || !text.trim()} onClick={download} className="bg-brand-600 hover:bg-brand-800">
          <Presentation size={15} /> {busy ? "Building…" : "Download .pptx"}
        </Button>
      </CardContent>
    </Card>
  );
}
