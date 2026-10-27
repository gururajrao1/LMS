"use client";

import { FormEvent, useEffect, useState } from "react";
import { CheckCircle2, CircleAlert, GitBranch, Link2, Mail, MessageSquarePlus, ScanSearch, Send, ShieldAlert, ShieldCheck, Undo2, UserRoundCheck, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import { AuditAction, AuditEntry, Challenge, CommentEvidence, CourseReview, getJson, Override, Person, ReviewComment, sendJson, Severity, Unverified } from "@/lib/api";
import { ROLE_LABEL } from "@/components/app-shell";
import { PromptDialog } from "@/components/prompt-dialog";
import { ScanLine } from "lucide-react";
import { Stat } from "@/components/app-shell";

/**
 * Checks whose finding names a document rather than a form of words. Only these
 * can be settled by citing something better; an overreach has to be rewritten by
 * a person, and offering a one-click fix there would misrepresent what it does.
 * Mirrors `judge.REPOINTABLE`.
 */
const REPOINTABLE = new Set(["quote_not_found", "quote_not_verbatim", "untraceable", "promotional_only"]);

const SEVERITY: Record<Severity, { label: string; className: string }> = {
  blocking: { label: "Blocking", className: "bg-danger-50 text-danger-700" },
  major: { label: "Major", className: "bg-warn-50 text-warn-700" },
  minor: { label: "Minor", className: "bg-stone-100 text-stone-600" },
};

const STATUS: Record<ReviewComment["status"], string> = {
  open: "Open",
  addressed: "Addressed, awaiting version",
  dismissed: "Dismissed",
  closed: "Closed",
};

const AUDIT_ICON: Record<AuditAction, typeof GitBranch> = {
  "review.assigned": UserRoundCheck,
  "comment.raised": MessageSquarePlus,
  "comment.resolved": CheckCircle2,
  "dismissal.challenged": ShieldAlert,
  "dismissal.overridden": ShieldAlert,
  "citation.repointed": Link2,
  "fix.unverified": ShieldAlert,
  "version.cut": GitBranch,
  "signoff.recorded": ShieldCheck,
  "course.published": Send,
};

function when(value: string | null) {
  return value ? new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "";
}

/**
 * The evidence behind one machine finding, opened in place.
 *
 * The load-bearing part is the quote: rendered span by span, so "12% verbatim"
 * stops being a number the reviewer has to take on faith and becomes a sentence
 * where the invented half is visibly struck through. What we could not check is
 * stated in the same breath, because a silent gap is the failure mode this whole
 * surface exists to prevent.
 */
function EvidencePanel({ runId, commentId }: { runId: string; commentId: string }) {
  const [evidence, setEvidence] = useState<CommentEvidence | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getJson<CommentEvidence>(`/api/runs/${runId}/review/comments/${commentId}/evidence`)
      .then(setEvidence)
      .catch(() => setError("No stored evidence for this comment."));
  }, [runId, commentId]);

  if (error) return <p className="mt-3 text-sm text-stone-600">{error}</p>;
  if (!evidence) return <p className="mt-3 text-sm text-stone-600">Loading the evidence…</p>;

  return (
    <div className="mt-3 space-y-4 rounded-xl border bg-surface-sunk p-4">
      {evidence.claim && (
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-stone-500">As written in the course</p>
          <p className="mt-1 text-sm leading-6 text-stone-800">{evidence.claim}</p>
        </div>
      )}

      {evidence.quote && (
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-stone-500">
            Recorded quote
            {evidence.match_percent !== null && (
              <span className="ml-2 font-semibold tabular-nums text-stone-700">{evidence.match_percent}% in the source</span>
            )}
          </p>
          <p className="mt-1 text-sm leading-7">
            {evidence.spans.map((span, index) => (
              <span key={index} className={span.present
                ? "bg-brand-50 text-brand-900"
                : "bg-danger-50 text-danger-800 line-through decoration-danger-400"}>
                {span.text}{" "}
              </span>
            ))}
          </p>
          <p className="mt-2 text-xs text-stone-600">
            Struck-through text does not appear in the stored document.
          </p>
        </div>
      )}

      {evidence.passage && (
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-stone-500">
            The stored document{evidence.source?.locator ? ` · ${evidence.source.locator}` : ""}
          </p>
          <p className="mt-1 max-h-40 overflow-y-auto rounded-lg bg-white p-3 text-sm leading-6 text-stone-700">
            {evidence.passage}
          </p>
        </div>
      )}

      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-stone-500">
          Citations · {evidence.coverage.held} of {evidence.coverage.total} checkable
        </p>
        <ul className="mt-1 space-y-1.5">
          {evidence.citations.map((citation, index) => (
            <li key={index} className="flex items-start gap-2 text-sm leading-6">
              <span className={`mt-1.5 size-2 shrink-0 rounded-full ${citation.held ? "bg-brand-600" : "bg-stone-300"}`} />
              <span className="min-w-0">
                <a href={citation.url} target="_blank" rel="noreferrer" className="text-stone-800 underline-offset-2 hover:underline">
                  {citation.title || citation.url}
                </a>
                {citation.locator && <span className="text-stone-600"> · {citation.locator}</span>}
                {!citation.traceable && <span className="text-danger-700"> · not in the research dossier</span>}
                {!citation.held && <span className="text-stone-600"> · no stored document, so never checked</span>}
              </span>
            </li>
          ))}
        </ul>
      </div>

      {evidence.suggested_rewrite && (
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-stone-500">Suggested wording</p>
          <p className="mt-1 text-sm leading-6 text-stone-800">{evidence.suggested_rewrite}</p>
        </div>
      )}
    </div>
  );
}

/**
 * A dismissal the machine would not accept. Deliberately the loudest thing on the
 * page: it is the one moment the software contradicts a domain expert, and it can
 * only do that because it is not offering an opinion — the quote is either in the
 * stored document or it is not.
 */
function ChallengeBanner({ challenge }: { challenge: Challenge }) {
  return (
    <div className="mt-3 rounded-xl border border-warn-200 bg-warn-50 p-4">
      <p className="flex items-center gap-2 font-medium text-warn-800">
        <ShieldAlert size={16} /> This dismissal was not accepted
      </p>
      <p className="mt-2 text-sm leading-6 text-warn-800">
        {challenge.by_name} dismissed this as “{challenge.attempted_reason}”. The{" "}
        <code className="rounded bg-warn-100 px-1 py-0.5 text-xs">{challenge.check}</code> check re-ran against the
        stored sources and still fails, so this is not a judgement call.
      </p>
      <p className="mt-2 text-sm leading-6 text-stone-700">{challenge.message}</p>
      {challenge.source_text && (
        <p className="mt-2 rounded-lg bg-white/70 p-3 text-xs leading-5 text-stone-600">
          <b className="text-stone-700">Recorded quote:</b> “{challenge.source_text}”
        </p>
      )}
      <p className="mt-3 flex items-start gap-2 text-sm leading-6 text-warn-800">
        <ScanSearch size={16} className="mt-1 shrink-0" />
        <span>
          Two ways forward: add the source document that contains this, and the check clears itself — or record an
          override, which is permitted and permanently attributed.
        </span>
      </p>
    </div>
  );
}

/**
 * A fix that was claimed but not found in the content. Raised by the version cut,
 * which is the last moment "we fixed it" can still be read against what is there.
 */
function UnverifiedNote({ unverified }: { unverified: Unverified }) {
  return (
    <div className="mt-3 rounded-xl border border-warn-200 bg-warn-50 p-4">
      <p className="flex items-center gap-2 font-medium text-warn-800">
        <ShieldAlert size={16} /> This was marked addressed, but the fix is not in the content
      </p>
      <p className="mt-2 text-sm leading-6 text-warn-800">
        Cutting v{unverified.version} re-read the assets and the{" "}
        <code className="rounded bg-warn-100 px-1 py-0.5 text-xs">{unverified.check}</code> check still fails, so the
        comment was reopened rather than closed into the version.
      </p>
      <p className="mt-2 text-sm leading-6 text-stone-700">{unverified.message}</p>
    </div>
  );
}

/** An override that was carried through. Never hidden, including after publication. */
function OverrideNote({ override }: { override: Override }) {
  return (
    <div className="mt-3 rounded-xl border border-stone-300 bg-stone-50 p-4">
      <p className="flex items-center gap-2 text-sm font-medium text-stone-800">
        <ShieldAlert size={15} /> Override recorded — the {override.check} check still fails
      </p>
      <p className="mt-2 text-sm leading-6 text-stone-700">{override.reason}</p>
      <p className="mt-1 text-xs text-stone-600">
        {override.actor_name}{override.actor_title ? ` · ${override.actor_title}` : ""} · {when(override.at)}
      </p>
    </div>
  );
}

/**
 * The governance trail. Append-only on the server, so this is a plain reverse
 * chronology with no controls — there is deliberately nothing here to edit.
 * The checker wears the signal hue, the same as everywhere else it appears.
 */
function AuditTrail({ audit }: { audit: AuditEntry[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Activity</CardTitle>
        <p className="text-sm text-stone-600">Every governance step, in order. Entries are never edited or removed.</p>
      </CardHeader>
      <CardContent>
        {audit.length ? (
          <ol className="max-h-96 space-y-3 overflow-y-auto pr-1">
            {[...audit].reverse().map((entry) => {
              const Icon = AUDIT_ICON[entry.action] ?? CheckCircle2;
              const machine = entry.actor_role === "checker";
              const dismissed = entry.detail.now === "dismissed";
              return (
                <li key={entry.id} className="flex gap-3">
                  <span className={`mt-0.5 grid size-7 shrink-0 place-items-center rounded-full ${
                    machine ? "bg-signal-50 text-signal-700" : "bg-stone-100 text-stone-600"}`}>
                    {dismissed ? <X size={14} /> : <Icon size={14} />}
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm leading-5">{entry.summary}</p>
                    <p className="mt-0.5 text-xs text-stone-600">
                      {entry.actor_title || entry.actor_role} · {when(entry.at)}
                    </p>
                    {typeof entry.detail.resolution === "string" && (
                      <p className="mt-1 text-xs leading-5 text-stone-600">“{entry.detail.resolution}”</p>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
        ) : (
          <p className="text-sm text-stone-600">Nothing recorded yet for this course.</p>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * Who owns this review.
 *
 * The queue was a list of everything unreviewed shown identically to every
 * reviewer, which tells five people that something needs doing and none of them
 * that it is theirs. Assigning does not lock anyone out — any reviewer may still
 * open any course, because a hard lock strands a course whose named expert is on
 * leave. It changes whose dashboard says the course is waiting on them.
 */
function AssignReviewers({ runId, user, review, busy, act }: {
  runId: string;
  user: Person;
  review: CourseReview;
  busy: boolean;
  act: (action: () => Promise<unknown>) => Promise<void>;
}) {
  const assignment = review.review_assignment;
  const [people, setPeople] = useState<Person[]>([]);
  const [chosen, setChosen] = useState<string[]>(assignment?.reviewers ?? []);
  const [note, setNote] = useState(assignment?.note ?? "");

  useEffect(() => {
    getJson<Person[]>("/api/people")
      .then((roster) => setPeople(roster.filter((person) => person.role === "reviewer")))
      .catch(() => undefined);
  }, []);

  const named = (id: string) => people.find((person) => person.id === id);
  const toggle = (id: string) =>
    setChosen((current) => current.includes(id) ? current.filter((entry) => entry !== id) : [...current, id]);

  // A reviewer sees who is on it, not the controls to change it.
  if (user.role !== "admin") {
    if (!assignment?.reviewers.length) return null;
    const mine = assignment.reviewers.includes(user.id);
    return (
      <Card>
        <CardHeader><CardTitle className="text-base">Review assignment</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {mine && (
            <p className="flex items-center gap-2 rounded-lg bg-brand-50 p-3 text-sm text-brand-800">
              <UserRoundCheck size={16} /> {assignment.assigned_by} asked you to review v{assignment.version}.
            </p>
          )}
          <ul className="space-y-1 text-sm text-stone-600">
            {assignment.reviewers.map((id) => (
              <li key={id}>{named(id)?.name ?? id}{id === user.id ? " (you)" : ""}</li>
            ))}
          </ul>
          {assignment.note && <p className="text-sm leading-6 text-stone-700">“{assignment.note}”</p>}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader><CardTitle className="text-base">{assignment ? "Reassign the review" : "Assign reviewers"}</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <div className="space-y-2">
          {people.map((person) => (
            <label key={person.id}
              className={`flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition-colors ${chosen.includes(person.id) ? "border-brand-600 bg-brand-50" : "hover:bg-stone-50"}`}>
              <input type="checkbox" checked={chosen.includes(person.id)} onChange={() => toggle(person.id)} className="mt-1 size-4 accent-brand-600" />
              <span>
                <span className="block text-sm font-medium">{person.name}</span>
                <span className="block text-xs text-stone-600">{person.title || ROLE_LABEL[person.role]}</span>
              </span>
            </label>
          ))}
          {!people.length && <p className="text-sm text-stone-600">Loading the reviewer roster…</p>}
        </div>
        <Textarea value={note} onChange={(event) => setNote(event.target.value)} rows={2} placeholder="What should they look at first?" />
        <Button disabled={busy || !chosen.length} className="w-full bg-brand-600 hover:bg-brand-800"
          onClick={() => act(() => sendJson(`/api/runs/${runId}/review/assign`, { user_id: user.id, reviewer_ids: chosen, note }))}>
          <UserRoundCheck /> Request review from {chosen.length || "…"} reviewer(s)
        </Button>
        {assignment && (
          <div className="space-y-2 border-t pt-3">
            <p className="text-xs font-medium uppercase tracking-wide text-stone-600">Notifications sent</p>
            {assignment.notifications.map((entry) => (
              <p key={entry.to} className="flex items-start gap-2 text-xs text-stone-600">
                <Mail size={13} className="mt-0.5 shrink-0" /> {entry.name} · {entry.to}
              </p>
            ))}
            {/* Same honesty as the publication panel: the record is real, the email is not. */}
            <p className="text-xs text-stone-500">Recorded on the course. Nothing is emailed in the demo.</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/** A written reason the page is waiting on, and which comment it belongs to. */
type Ask = { kind: "addressed" | "dismiss" | "override"; comment: ReviewComment };

/**
 * What each reason is for, in the reader's terms.
 *
 * The override copy names the check being overruled rather than saying "this
 * check": someone recording a permanent, attributed decision should be able to
 * see what they are overruling without closing the box to go and look.
 */
function askCopy(ask: Ask) {
  const { kind, comment } = ask;
  if (kind === "addressed") {
    return {
      title: "How was this addressed?",
      description: "Cutting a version re-reads the content and re-runs the checks behind machine findings, so a fix that did not land will reopen this comment rather than close it.",
      label: "What changed",
      placeholder: "Added the dose-modification table as slide 12, cited to Section 2.2 of the label.",
      confirmLabel: "Mark addressed",
      destructive: false,
    };
  }
  if (kind === "dismiss") {
    return {
      title: "Why is this being dismissed?",
      description: comment.origin === "automated_check"
        ? `This is a ${comment.check} finding. If the check still fails against the stored sources, the dismissal is challenged and the comment stays open until you record an override.`
        : "The comment is closed without a version bump. The reason is kept with it.",
      label: "Reason",
      placeholder: "Not applicable to this audience; the point is covered on slide 4.",
      confirmLabel: "Dismiss",
      destructive: false,
    };
  }
  return {
    title: "Record an override",
    description: `The ${comment.check} check still fails against the stored sources. Overriding is always allowed and never silent: this is permanent, attributed to you by name and title, and shown on the published course.`,
    label: "Why is it correct to publish with this check still failing?",
    placeholder: "Checked Section 5.1 of the Prescribing Information by hand. The excerpt is faithful and the break between paragraphs is not material.",
    confirmLabel: "Record the override",
    destructive: true,
  };
}

export function CourseReviewPanel({ runId, user, onChange }: { runId: string; user: Person; onChange?: (review: CourseReview) => void }) {
  const [review, setReview] = useState<CourseReview | null>(null);
  const [target, setTarget] = useState("deck");
  const [severity, setSeverity] = useState<Severity>("major");
  const [body, setBody] = useState("");
  const [summary, setSummary] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [showEvidence, setShowEvidence] = useState<string | null>(null);
  const [repointed, setRepointed] = useState<{ id: string; title: string } | null>(null);
  const [ask, setAsk] = useState<Ask | null>(null);

  const apply = (next: CourseReview) => { setReview(next); onChange?.(next); };
  const reload = async () => apply(await getJson<CourseReview>(`/api/runs/${runId}/review`));

  useEffect(() => { getJson<CourseReview>(`/api/runs/${runId}/review`).then(apply).catch(() => setError("Could not load the review.")); }, [runId]); // eslint-disable-line react-hooks/exhaustive-deps

  async function act(action: () => Promise<unknown>) {
    setBusy(true); setError("");
    try { await action(); await reload(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "That did not work"); }
    finally { setBusy(false); }
  }

  /** One place every written reason is sent from, so the dialog stays generic. */
  async function submitAsk(reason: string) {
    if (!ask) return;
    const { kind, comment } = ask;
    const url = `/api/runs/${runId}/review/comments/${comment.id}`;
    await act(() => sendJson(url, kind === "override"
      ? { user_id: user.id, status: "dismissed", resolution: comment.challenge!.attempted_reason, override_reason: reason }
      : { user_id: user.id, status: kind === "addressed" ? "addressed" : "dismissed", resolution: reason },
      "PATCH"));
    setAsk(null);
  }

  async function addComment(event: FormEvent) {
    event.preventDefault();
    await act(async () => {
      await sendJson(`/api/runs/${runId}/review/comments`, { user_id: user.id, target, severity, body });
      setBody("");
    });
  }

  if (!review) return <Card><CardContent className="p-8 text-center text-stone-600">{error || "Loading the review…"}</CardContent></Card>;

  // Anyone in the workspace can raise a comment, but only a reviewer can clear the
  // course for the field — the admin who addresses the comments must not sign them off.
  const canComment = user.role === "reviewer" || user.role === "admin";
  const canSignoff = user.role === "reviewer";
  const isAdmin = user.role === "admin";
  // The maker fixes content, so only the admin marks a comment addressed. Judging
  // one away is a reviewer's call too, and it is now recorded against whoever made it.
  const canJudge = isAdmin || user.role === "reviewer";
  const open = review.comments.filter((comment) => comment.status === "open");
  const addressed = review.comments.filter((comment) => comment.status === "addressed");
  const settled = review.comments.filter((comment) => ["closed", "dismissed"].includes(comment.status));
  const mySignoff = review.signoffs.find((entry) => entry.author_id === user.id && entry.version === review.version);

  return (
    <div className="space-y-5">
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat icon={MessageSquarePlus} value={open.length} label="Open comments" tone={open.length ? "warn" : "brand"} />
        <Stat icon={CircleAlert} value={review.readiness.open_blocking} label="Blocking" tone={review.readiness.open_blocking ? "warn" : "brand"} />
        {/* Only worth a tile when there is something to say — an empty "0 challenged"
            reads as a system that has never had to hold anyone back. */}
        {review.readiness.challenged || review.readiness.overrides ? (
          <Stat icon={ShieldAlert} tone="warn"
            value={review.readiness.challenged || review.readiness.overrides}
            label={review.readiness.challenged ? "Dismissals held" : "Overrides on record"} />
        ) : (
          <Stat icon={GitBranch} value={`v${review.version}`} label="Current version" tone="brand" />
        )}
        <Stat icon={ShieldCheck} value={review.readiness.approvals} label="Sign-offs at this version" />
      </section>

      {error && <p className="text-sm text-danger-600">{error}</p>}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-5">
          {canComment && (
            <Card>
              <CardHeader><CardTitle className="text-base">Raise a review comment</CardTitle></CardHeader>
              <CardContent>
                <form onSubmit={addComment} className="space-y-4">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div>
                      <label htmlFor="review-target" className="text-sm font-medium">Asset</label>
                      <NativeSelect id="review-target" value={target} onChange={(event) => setTarget(event.target.value)} className="mt-2">
                        {review.targets.map((entry) => <option key={entry.id} value={entry.id}>{entry.title}</option>)}
                      </NativeSelect>
                    </div>
                    <div>
                      <label htmlFor="review-severity" className="text-sm font-medium">Severity</label>
                      <NativeSelect id="review-severity" value={severity} onChange={(event) => setSeverity(event.target.value as Severity)} className="mt-2">
                        <option value="blocking">Blocking — must fix before publication</option>
                        <option value="major">Major</option>
                        <option value="minor">Minor</option>
                      </NativeSelect>
                    </div>
                  </div>
                  <div>
                    <label htmlFor="review-body" className="text-sm font-medium">Comment</label>
                    <Textarea id="review-body" value={body} onChange={(event) => setBody(event.target.value)} rows={3} className="mt-2" placeholder="What needs to change, and why?" />
                  </div>
                  <Button type="submit" disabled={busy || !body.trim()} className="bg-brand-600 hover:bg-brand-800"><MessageSquarePlus /> Add comment</Button>
                </form>
              </CardContent>
            </Card>
          )}

          {[["Open", open], ["Addressed", addressed], ["Resolved", settled]].map(([label, list]) => {
            const comments = list as ReviewComment[];
            if (!comments.length) return null;
            return (
              <Card key={label as string}>
                <CardHeader><CardTitle className="text-base">{label as string} ({comments.length})</CardTitle></CardHeader>
                <CardContent className="space-y-3">
                  {comments.map((comment) => (
                    <div key={comment.id} className="rounded-xl border p-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge className={SEVERITY[comment.severity].className}>{SEVERITY[comment.severity].label}</Badge>
                        <Badge variant="outline">{review.targets.find((entry) => entry.id === comment.target)?.title ?? comment.target}</Badge>
                        <span className="text-xs text-stone-600">v{comment.version} · {STATUS[comment.status]}</span>
                        {/* Signal hue, same as the Checks tab: a machine finding
                            should never read as a colleague's comment. */}
                        {comment.origin === "automated_check" && (
                          <Badge variant="outline" className="gap-1 border-signal-100 bg-signal-50 text-signal-700"><ScanLine size={11} /> automated</Badge>
                        )}
                      </div>
                      <p className="mt-3 whitespace-pre-line leading-6">{comment.body}</p>
                      <p className="mt-2 text-xs text-stone-600">{comment.author_name} · {comment.author_title} · {when(comment.created_at)}</p>
                      {comment.resolution && (
                        <div className="mt-3 rounded-lg bg-brand-50 p-3 text-sm text-brand-800">
                          <p><b>Resolution:</b> {comment.resolution}</p>
                          {comment.resolved_by_name && (
                            <p className="mt-1 text-xs text-brand-700">
                              {comment.resolved_by_name}
                              {comment.resolved_by_title ? ` · ${comment.resolved_by_title}` : ""}
                              {comment.resolved_at ? ` · ${when(comment.resolved_at)}` : ""}
                            </p>
                          )}
                        </div>
                      )}
                      {/* Only a machine finding has stored evidence behind it; a
                          colleague's comment is its own evidence. */}
                      {comment.origin === "automated_check" && (
                        <button type="button"
                          onClick={() => setShowEvidence(showEvidence === comment.id ? null : comment.id)}
                          className="mt-2 flex items-center gap-1.5 text-sm font-medium text-signal-700 hover:text-signal-800">
                          <ScanSearch size={15} />
                          {showEvidence === comment.id ? "Hide the evidence" : "Show me the evidence"}
                        </button>
                      )}
                      {showEvidence === comment.id && <EvidencePanel runId={runId} commentId={comment.id} />}
                      {comment.challenge && <ChallengeBanner challenge={comment.challenge} />}
                      {comment.unverified && comment.status === "open" && <UnverifiedNote unverified={comment.unverified} />}
                      {comment.override && <OverrideNote override={comment.override} />}
                      {repointed?.id === comment.id && (
                        <p className="mt-3 flex items-start gap-2 rounded-lg bg-signal-50 p-3 text-sm text-signal-800">
                          <Link2 size={15} className="mt-0.5 shrink-0" />
                          Now cited to <b>{repointed.title}</b>. Cutting the next version re-runs this
                          check against the changed content, so the fix has to hold.
                        </p>
                      )}
                      {canJudge && comment.status !== "closed" && (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {/* The one fix a citation finding actually has. Offered only
                              where it is true: a wording problem cannot be solved by
                              citing a different document, so those findings do not get
                              a button that implies it can. */}
                          {isAdmin && comment.status === "open" && REPOINTABLE.has(comment.check ?? "") && (
                            <Button size="sm" variant="outline" disabled={busy}
                              className="border-signal-200 text-signal-700 hover:bg-signal-50"
                              onClick={() => act(async () => {
                                const next = await sendJson<{ citation: { title: string } } & CourseReview>(
                                  `/api/runs/${runId}/review/comments/${comment.id}/repoint`, { user_id: user.id });
                                setRepointed({ id: comment.id, title: next.citation.title });
                              })}><Link2 /> Repoint the citation</Button>
                          )}
                          {isAdmin && comment.status !== "addressed" && (
                            <Button size="sm" variant="outline" disabled={busy}
                              onClick={() => setAsk({ kind: "addressed", comment })}><CheckCircle2 /> Mark addressed</Button>
                          )}
                          {comment.status === "open" && !comment.challenge && (
                            <Button size="sm" variant="ghost" disabled={busy}
                              onClick={() => setAsk({ kind: "dismiss", comment })}><X /> Dismiss</Button>
                          )}
                          {comment.status === "open" && comment.challenge && (
                            <Button size="sm" variant="outline" disabled={busy}
                              className="border-warn-200 text-warn-800 hover:bg-warn-50"
                              onClick={() => setAsk({ kind: "override", comment })}><ShieldAlert /> Record an override</Button>
                          )}
                          {comment.status !== "open" && (
                            <Button size="sm" variant="ghost" disabled={busy} onClick={() => act(() => sendJson(
                              `/api/runs/${runId}/review/comments/${comment.id}`, { user_id: user.id, status: "open" }, "PATCH",
                            ))}><Undo2 /> Reopen</Button>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </CardContent>
              </Card>
            );
          })}

          {!review.comments.length && (
            <Card><CardContent className="p-8 text-center text-stone-600">No review comments yet. The first draft is waiting for a domain expert.</CardContent></Card>
          )}
        </div>

        <div className="space-y-5">
          <AssignReviewers runId={runId} user={user} review={review} busy={busy} act={act} />

          {canSignoff && (
            <Card>
              <CardHeader><CardTitle className="text-base">Your sign-off</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                {mySignoff
                  ? <p className="rounded-lg bg-brand-50 p-3 text-sm text-brand-800">You recorded <b>{mySignoff.decision === "approved" ? "approval" : "changes requested"}</b> for v{review.version}.{mySignoff.note ? ` “${mySignoff.note}”` : ""}</p>
                  : <p className="text-sm text-stone-600">Record a decision for version {review.version}.</p>}
                <Textarea value={note} onChange={(event) => setNote(event.target.value)} rows={2} placeholder="Optional note" />
                <div className="flex gap-2">
                  <Button disabled={busy} className="bg-brand-600 hover:bg-brand-800" onClick={() => act(() => sendJson(`/api/runs/${runId}/review/signoff`, { user_id: user.id, decision: "approved", note }))}>
                    <ShieldCheck /> Approve
                  </Button>
                  <Button disabled={busy} variant="outline" onClick={() => act(() => sendJson(`/api/runs/${runId}/review/signoff`, { user_id: user.id, decision: "changes_requested", note }))}>
                    Request changes
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {isAdmin && (
            <Card>
              <CardHeader><CardTitle className="text-base">Cut a new version</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-stone-600">{addressed.length ? `${addressed.length} addressed comment(s) will close into v${review.version + 1}.` : "Mark at least one comment addressed first."}</p>
                <Input value={summary} onChange={(event) => setSummary(event.target.value)} placeholder="What changed in this version?" />
                <Button disabled={busy || !addressed.length} className="w-full bg-brand-600 hover:bg-brand-800"
                  onClick={() => act(async () => { await sendJson(`/api/runs/${runId}/review/versions`, { user_id: user.id, summary }); setSummary(""); })}>
                  <GitBranch /> Publish version {review.version + 1}
                </Button>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader><CardTitle className="text-base">Version history</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              {[...review.versions].reverse().map((entry) => (
                <div key={entry.version} className="flex gap-3">
                  <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-full bg-brand-50 text-xs font-semibold text-brand-700">v{entry.version}</span>
                  <div>
                    <p className="text-sm font-medium leading-5">{entry.summary}</p>
                    <p className="mt-1 text-xs text-stone-600">{entry.author_name}{entry.created_at ? ` · ${when(entry.created_at)}` : ""}{entry.addressed.length ? ` · ${entry.addressed.length} comment(s) closed` : ""}</p>
                    {entry.unverified?.length ? (
                      <p className="mt-1 text-xs font-medium text-warn-700">
                        {entry.unverified.length} claimed fix(es) did not clear their checks and were reopened
                      </p>
                    ) : null}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          {review.signoffs.length > 0 && (
            <Card>
              <CardHeader><CardTitle className="text-base">Sign-offs</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                {[...review.signoffs].reverse().map((entry) => (
                  <div key={entry.id} className="rounded-lg border p-3">
                    <p className="text-sm font-medium">{entry.author_name} · v{entry.version}</p>
                    <p className="text-xs text-stone-600">{entry.author_title}</p>
                    <Badge className={`mt-2 ${entry.decision === "approved" ? "bg-brand-50 text-brand-700" : "bg-warn-50 text-warn-700"}`}>
                      {entry.decision === "approved" ? "Approved" : "Changes requested"}
                    </Badge>
                    {entry.note && <p className="mt-2 text-sm leading-6 text-stone-600">{entry.note}</p>}
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          <AuditTrail audit={review.audit ?? []} />
        </div>
      </div>

      {/* One dialog for every written reason on the page, so only the pending
          question is ever mounted. */}
      {ask && (
        <PromptDialog
          open
          busy={busy}
          onConfirm={submitAsk}
          onCancel={() => setAsk(null)}
          {...askCopy(ask)}
        />
      )}
    </div>
  );
}
