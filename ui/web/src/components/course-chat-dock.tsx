"use client";

import { useEffect, useState } from "react";
import { MessageSquareText } from "lucide-react";
import { CourseChat } from "@/components/course-chat";
import { Learner } from "@/lib/api";

/**
 * The assistant as a full-height right-hand drawer rather than a tab.
 *
 * Asking a question is something you do *while* reading a slide or judging a
 * comment, so it should not cost you the page you are on. Open, it sets
 * `data-dock-open` on the document; the shell reads that and insets its main
 * column by the drawer's width, so the drawer sits beside the content instead
 * of on top of it. Below `lg` there is no room to inset, so it overlays.
 */
export function CourseChatDock({ runId, learner, context, userId, title, blurb }: {
  runId: string;
  learner: Learner;
  /** Which surface the reader is on, so the starters match the page. */
  context?: string;
  /** Set for a trainee, so record answers are about them rather than the cohort. */
  userId?: string;
  title?: string;
  blurb?: string;
}) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const root = document.documentElement;
    if (open) root.dataset.dockOpen = "true";
    else delete root.dataset.dockOpen;
    return () => { delete root.dataset.dockOpen; };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [open]);

  return (
    <>
      <aside
        aria-hidden={!open}
        aria-label={title ?? "Ask the course"}
        className={`fixed inset-y-0 right-0 z-50 w-[min(23rem,100vw)] border-l border-line bg-white shadow-2xl transition-transform duration-200 print:hidden ${open ? "translate-x-0" : "pointer-events-none translate-x-full"}`}
      >
        {open && (
          <CourseChat runId={runId} learner={learner} context={context} userId={userId} title={title} blurb={blurb} fill onClose={() => setOpen(false)} />
        )}
      </aside>

      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="dock-launcher fixed bottom-5 right-5 z-50 flex items-center gap-2 rounded-full bg-surface-deep py-3 pl-4 pr-5 text-sm font-semibold text-white shadow-lg transition-all hover:bg-brand-800 active:translate-y-px print:hidden"
        >
          <MessageSquareText size={17} /> Ask
        </button>
      )}
    </>
  );
}
