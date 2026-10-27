"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Textarea } from "@/components/ui/textarea";

/**
 * Asking for a written reason, in the page rather than in the browser chrome.
 *
 * Every one of these prompts records something permanent and attributed — a
 * resolution, a dismissal, an override that gets printed on the published course.
 * `window.prompt` gave a one-line unstyled box with no room to read what you were
 * agreeing to, no way to see the finding you were judging, and a Cancel that looked
 * identical to OK. What is being written down deserves the same weight on screen.
 *
 * Mounted per question rather than kept around and toggled — `{ask && <PromptDialog …>}`.
 * That is what keeps the field empty: a reason of record must never inherit the last
 * one and attribute the wrong words to someone, and mounting fresh guarantees it
 * without a reset effect racing the render that opened the box.
 */
export function PromptDialog({
  open,
  title,
  description,
  label,
  placeholder,
  confirmLabel,
  destructive = false,
  busy = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  description?: string;
  label: string;
  placeholder?: string;
  confirmLabel: string;
  /** Marks an action that is permanent and attributed, not merely a save. */
  destructive?: boolean;
  busy?: boolean;
  onConfirm: (value: string) => void;
  onCancel: () => void;
}) {
  const [value, setValue] = useState("");
  const field = useRef<HTMLTextAreaElement>(null);

  // Focus after the open animation, or the caret lands mid-transition.
  useEffect(() => {
    const id = window.setTimeout(() => field.current?.focus(), 60);
    return () => window.clearTimeout(id);
  }, []);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!value.trim() || busy) return;
    onConfirm(value.trim());
  }

  return (
    <AlertDialog open={open} onOpenChange={(next) => { if (!next) onCancel(); }}>
      <AlertDialogContent className="sm:max-w-lg">
        <form onSubmit={submit} className="contents">
          <AlertDialogHeader>
            <AlertDialogTitle>{title}</AlertDialogTitle>
            {description && <AlertDialogDescription>{description}</AlertDialogDescription>}
          </AlertDialogHeader>

          <div className="space-y-2 text-left">
            <label htmlFor="prompt-dialog-value" className="text-sm font-medium">{label}</label>
            <Textarea
              id="prompt-dialog-value"
              ref={field}
              rows={4}
              value={value}
              placeholder={placeholder}
              onChange={(event) => setValue(event.target.value)}
              // Enter alone would submit a paragraph halfway through a sentence.
              onKeyDown={(event) => {
                if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) submit(event);
              }}
            />
            <p className="text-xs text-stone-600">This is stored on the course and attributed to you.</p>
          </div>

          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              type="submit"
              disabled={busy || !value.trim()}
              className={destructive ? "bg-warn-600 text-white hover:bg-warn-700" : "bg-brand-600 text-white hover:bg-brand-800"}
            >
              {busy ? "Saving…" : confirmLabel}
            </AlertDialogAction>
          </AlertDialogFooter>
        </form>
      </AlertDialogContent>
    </AlertDialog>
  );
}
