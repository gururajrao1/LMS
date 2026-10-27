export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Run = {
  id: string;
  status: "queued" | "running" | "completed" | "failed";
  progress: number;
  current_stage?: string;
  mode?: "live" | "local" | "replay";
};

export type Citation = { source_id?: string; title?: string; url?: string; locator: string };

export type QuizQuestion = { id: string; prompt: string; options: string[]; correct_index: number; rationale: string; citations: Citation[] };

export type CourseTrack = {
  videos: { id: string; title: string; url: string }[];
  faq: { items: { question: string; answer: string; nuance?: string; escalation?: string; citations: Citation[] }[] };
  quiz: { passing_score: number; questions: QuizQuestion[] };
  storyboard: {
    estimated_duration_seconds: number;
    scenes: { id: number; duration_seconds: number; title: string; narration: string; visual: string; on_screen_text: string; citations: Citation[] }[];
  };
  deck: { slides: { number: number; title: string; purpose: string; citations?: Citation[] }[] };
  pptx_url: string;
};

export type Drug = { brand: string; generic: string; area: string };

export type SourceList = { scope: string; sources: { source_id?: string; title: string; publisher?: string; version?: string; url: string }[] };

export type CourseContent = {
  manifest: { drug: Drug; citation_count: number };
  sources: SourceList;
  blueprint: { title: string; audiences: Record<string, string[]> };
  default_learner: Learner;
  learners: Record<Learner, CourseTrack>;
};

// "checker" is the automated pre-review identity: it authors comments but never signs in.
export type Role = "admin" | "reviewer" | "checker" | "msl" | "hcp";
export type Learner = "msl" | "hcp";
export type Person = { id: string; name: string; email: string; role: Role; title: string };

export type Severity = "blocking" | "major" | "minor";
export type CommentStatus = "open" | "addressed" | "dismissed" | "closed";

export type ReviewComment = {
  id: string;
  target: string;
  severity: Severity;
  body: string;
  status: CommentStatus;
  resolution: string | null;
  version: number;
  author_id: string;
  author_name: string;
  author_title: string;
  created_at: string;
  resolved_at: string | null;
  // Absent on comments settled before resolutions were attributed.
  resolved_by_id?: string | null;
  resolved_by_name?: string | null;
  resolved_by_title?: string | null;
  closed_in_version?: number;
  origin?: "automated_check";
  check?: string;
  finding_id?: string;
  // Present while a dismissal is held because the check it dismisses still fails.
  challenge?: Challenge;
  // Present once someone carried that dismissal through anyway, on the record.
  override?: Override;
  // Present when a version cut read the content and the claimed fix was not there.
  unverified?: Unverified;
};

export type Unverified = {
  at: string;
  version: number;
  check: string;
  reference: string;
  message: string;
  asset_text: string;
  source_text: string;
};

export type Challenge = {
  raised_at: string;
  by_id: string;
  by_name: string;
  by_title: string;
  attempted_reason: string;
  check: string;
  reference: string;
  message: string;
  asset_text: string;
  source_text: string;
};

export type Override = {
  reason: string;
  check: string;
  actor_id: string;
  actor_name: string;
  actor_title: string;
  at: string;
};

export type AuditAction =
  | "review.assigned" | "comment.raised" | "comment.resolved"
  | "dismissal.challenged" | "dismissal.overridden" | "citation.repointed"
  | "fix.unverified" | "version.cut" | "signoff.recorded" | "course.published";

/** One governance event. The trail is append-only: entries are never edited or removed. */
export type AuditEntry = {
  id: string;
  at: string;
  action: AuditAction;
  actor_id: string;
  actor_name: string;
  actor_title: string;
  actor_role: Role;
  summary: string;
  detail: Record<string, unknown>;
};

export type Signoff = { id: string; version: number; decision: "approved" | "changes_requested"; note: string; author_id: string; author_name: string; author_title: string; created_at: string };

export type CourseVersion = { version: number; summary: string; author_name: string; addressed: string[]; unverified?: string[]; created_at: string | null };

export type Publication = {
  version: number;
  published_at: string;
  published_by: string;
  starts_on: string;
  due_on: string;
  message: string;
  assignees: string[];
  notifications: { to: string; name: string; subject: string; sent_at: string }[];
  // Still-failing checks that were carried through deliberately. Absent on courses
  // published before overrides were recorded.
  overrides?: (Override & { comment_id: string; severity: Severity; target: string })[];
};

export type Readiness = { open_comments: number; open_blocking: number; challenged: number; overrides: number; addressed_comments: number; approvals: number; changes_requested: number; approved_by: string[]; can_publish: boolean };

/** Who the medical education lead put on this review, and when. */
export type ReviewAssignment = {
  version: number;
  assigned_at: string;
  assigned_by: string;
  reviewers: string[];
  note: string;
  notifications: { to: string; name: string; subject: string; sent_at: string }[];
};

export type CourseReview = {
  run_id: string;
  version: number;
  status: "draft" | "in_review" | "approved" | "published";
  comments: ReviewComment[];
  versions: CourseVersion[];
  signoffs: Signoff[];
  publication: Publication | null;
  readiness: Readiness;
  targets: { id: string; title: string }[];
  audit: AuditEntry[];
  review_assignment?: ReviewAssignment | null;
};

export type Certificate = {
  id: string;
  code: string;
  learner_name: string;
  learner_title: string;
  run_id: string;
  course_version: number;
  score: number;
  issued_at: string;
  expires_at?: string;
  approved_by?: { name: string; title: string }[];
  drug?: Drug;
  course_title?: string;
};

export type LearnerSummary = {
  stage: "not_started" | "baseline" | "learning" | "final" | "complete";
  modules_complete: number;
  modules_total: number;
  percent: number;
  baseline_score: number | null;
  final_score: number | null;
  uplift: number | null;
  passed: boolean;
  attempts: number;
  certificate: Certificate | null;
};

export type ModuleFeedback = { id: string; module_id: string; rating: number; comment: string; created_at: string };
export type LearnerModule = { id: string; title: string; kind: string; minutes: number; completed: boolean; feedback: ModuleFeedback | null };

/** Where a learner stands with one assignment. Derived, like the programme lifecycle. */
export type AssignmentState = "overdue" | "due" | "upcoming" | "completed";

export type Assignment = {
  run_id: string;
  drug: Drug;
  /** The training cycle this is, when the programme is one. The drug is separate. */
  title: string | null;
  version: number;
  starts_on: string;
  due_on: string;
  message: string;
  summary: LearnerSummary;
  state: AssignmentState;
  days_remaining: number | null;
  days_until_start: number | null;
};

export type LearnerHome = { user: Person; track: Learner; courses: Assignment[] };

export type LearnerCourse = {
  user: Person;
  track: Learner;
  manifest: { drug: Drug; citation_count: number };
  sources: SourceList;
  content: CourseTrack;
  publication: Publication;
  version: number;
  modules: LearnerModule[];
  summary: LearnerSummary;
};

export type Attempt = { id: string; kind: "baseline" | "final"; score: number; correct: number; total: number; passing_score: number; passed: boolean; created_at: string };

/**
 * A gamified question group. Its items are ordinary questions carrying `group` —
 * the server folds them into the same question list, so they are scored and
 * checked like everything else and the format is only how they are asked.
 *
 * `sort` is a triage board: two buckets, one finding at a time.
 * `assemble` is word building: a labelled instruction rebuilt from phrase chips.
 */
export type QuestionGroup = {
  id: string;
  kind: "sort" | "assemble";
  title: string;
  instruction: string;
  /** sort only. */
  buckets?: string[];
  /** assemble only. */
  items?: { id: string; prompt: string; tail: string; blanks: { id: string; before: string }[] }[];
};

/** A chart rendered from cited numbers — never a photograph, scan or histology image. */
export type Figure = {
  caption: string;
  chart_kind: "line" | "bar";
  x_title: string;
  y_title: string;
  y_suffix: string;
  series: { name: string; points: { label: string; value: number }[] }[];
};

export type AskedQuestion = {
  id: string; prompt: string; options: string[];
  group?: string | null; figure?: Figure | null;
};

export type Assessment = {
  kind: "baseline" | "final";
  title: string;
  passing_score: number;
  gated: boolean;
  /** Whether the server will fill unanswered questions on request. Demo only. */
  demo_fill?: boolean;
  groups: QuestionGroup[];
  questions: AskedQuestion[];
  attempts: Attempt[];
};

export type ReviewedQuestion = AskedQuestion & {
  chosen: number | null; correct_index: number; correct: boolean; rationale: string; citations: Citation[];
};

export type AssessmentResult = {
  attempt: Attempt;
  summary: LearnerSummary;
  groups: QuestionGroup[];
  review: ReviewedQuestion[];
};

export type CohortLearner = LearnerSummary & { user_id: string; name: string; role: Role; title: string };

export type Cohort = {
  run_id: string;
  assigned: number;
  started: number;
  certified: number;
  measured: number;
  average_baseline: number | null;
  average_final: number | null;
  average_uplift: number | null;
  learners: CohortLearner[];
  feedback: (ModuleFeedback & { name: string })[];
};

export type ChatReply = {
  answer: string;
  citations: Citation[];
  evidence: { section_title: string; text: string; citations: Citation[] }[];
  /** `record` is read straight off the programme's own data, with no model involved. */
  mode: "retrieval" | "model" | "record";
};

/** A reference document, and whether we hold it here rather than only linking to it. */
export type LibraryDocument = {
  key: string;
  title: string;
  url: string;
  publisher?: string;
  source_id?: string;
  kind?: string;
  fetched_at?: string;
  held: boolean;
  cited: boolean;
  /** How many entries in the source manifest collapsed into this one document. */
  listed_as: number;
};

export type Library = { drug: string; held: number; total: number; documents: LibraryDocument[] };

export type LibraryText = LibraryDocument & { text: string; characters: number };

/** Starters the server has already checked it can answer for this surface. */
export type ChatStarters = {
  context: string;
  starters: { question: string; kind: "dossier" | "record" }[];
};

export type CheckFinding = {
  id: string;
  unit_id: string;
  asset: "deck" | "quiz" | "faq" | "storyboard";
  reference: string;
  check: string;
  severity: Severity;
  message: string;
  asset_text: string;
  source_text: string;
  suggested_rewrite: string;
  citations: Citation[];
  promoted: CommentStatus | null;
};

export type Checks = {
  run_id: string;
  checked_at?: string;
  model_status?: Record<string, string>;
  stats: {
    units?: number;
    citations?: number;
    traceable?: number;
    checkable?: number;
    verified?: number;
    partial?: number;
    flagged_units?: number;
    coverage_percent?: number;
    verified_percent?: number;
  };
  findings: CheckFinding[];
  agreement: {
    raised: number;
    settled: number;
    accepted: number;
    dismissed: number;
    agreement_percent: number | null;
    /** Calibration, not a scorecard. `agreement_percent` is null below a usable sample. */
    by_reviewer?: {
      id: string;
      name: string;
      title: string;
      settled: number;
      accepted: number;
      dismissed: number;
      overrides: number;
      agreement_percent: number | null;
    }[];
  };
  /** Live corpus state — what could be checked today, as against when the report was written. */
  now?: {
    documents?: number;
    citations?: number;
    checkable?: number;
    verified?: number;
    partial?: number;
    coverage_percent?: number;
    verified_percent?: number;
  };
};

export type CoverageState = "covered" | "thin" | "missing";

export type CoverageCell = {
  state: CoverageState;
  total: number;
  units: { id: string; reference: string; asset: string; matched: string[] }[];
} | null;

export type CoverageGap = {
  finding_id: string;
  track: string;
  topic: string;
  title: string;
  why: string;
  state: CoverageState;
  units: number;
  expected: number;
  severity: Severity;
  promoted: CommentStatus | null;
};

/** Required topics against what the course actually covers — completeness, not accuracy. */
export type Completeness = {
  run_id: string;
  curriculum: { name: string; jurisdiction: string; reviewed_on: string; topics: number };
  tracks: string[];
  rows: {
    id: string;
    title: string;
    why: string;
    severity: Severity;
    min_units: number;
    tracks: Record<string, CoverageCell>;
  }[];
  stats: { required: number; covered: number; thin: number; missing: number; percent: number; missing_blocking: number };
  gaps: CoverageGap[];
};

export type Analytics = {
  run_id: string;
  funnel: { stage: string; count: number; percent: number }[];
  score_bands: { band: string; count: number }[];
  difficulty: { track: Learner; id: string; prompt: string; attempts: number; correct: number; percent: number }[];
  modules: { id: string; title: string; minutes: number; completed: number; rating: number | null; ratings: number }[];
  activity: { date: string; modules: number; assessments: number; certificates: number; cumulative_certified: number }[];
  roi: {
    measured: {
      generation_minutes: number | null;
      review_days: number | null;
      days_to_publish: number | null;
      agent_cost_usd: number;
      versions: number;
      expert_comments: number;
      reviewers: number;
      citations: number | null;
    };
    baseline: { first_version_days: number; update_days: number; review_cycle_days: number; blended_day_rate_usd: number };
    saving: { days_saved: number | null; percent_faster: number | null; cost_saved_usd: number | null; update_days_saved: number };
  };
  time_to_field: {
    phases: { phase: string; detail: string; measured_minutes: number | null; measured_days: number | null; manual_days: number }[];
    measured_total_days: number;
    manual_total_days: number;
  };
  unit_economics: {
    build_cost_usd: number;
    /** Expert-days the build was costed at — the floor when elapsed time was shorter. */
    expert_days_costed: number;
    floored: boolean;
    manual_build_cost_usd: number;
    certified: number;
    assigned: number;
    cost_per_certified_usd: number | null;
    manual_cost_per_certified_usd: number | null;
    curve: { learners: number; cost_usd: number | null; manual_cost_usd: number | null; measured: boolean }[];
    version_count: number;
  };
  speed_to_competence: {
    median_days: number | null;
    fastest_days: number | null;
    slowest_days: number | null;
    certified: number;
    outstanding: number;
    learners: { name: string; track: string; days: number | null; attempts: number }[];
  };
  uplift_by_track: { track: string; learners: number; baseline: number; final: number; uplift: number }[];
  checker_leverage: {
    units_checked: number | null;
    citations_checked: number | null;
    raised: number;
    accepted: number;
    dismissed: number;
    /** Null until enough findings are settled to make a rate mean anything. */
    agreement_percent: number | null;
    settled: number;
    min_for_rate: number;
    minutes_per_defect: number;
    reviewer_hours_saved: number;
    reviewer_cost_saved_usd: number;
    human_comments: number;
  };
};

/** Everything needed to settle one machine finding without leaving the comment. */
export type CommentEvidence = {
  comment_id: string;
  check: string;
  severity: Severity;
  reference: string;
  message: string;
  claim: string;
  suggested_rewrite: string;
  quote: string;
  spans: { text: string; present: boolean }[];
  match_percent: number | null;
  passage: string;
  source: { title: string; url: string; locator: string } | null;
  citations: { title: string; url: string; locator: string; traceable: boolean; held: boolean; claim: string }[];
  unheld: string[];
  coverage: { held: number; total: number };
};

export type ProgrammeState = "draft" | "scheduled" | "live" | "completed" | "archived";

/** A course in the field: published to a cohort, on a schedule, for one client. */
export type Programme = {
  run_id: string;
  client_id: string;
  drug: Drug;
  version: number;
  /** The training cycle this is, when the programme is one. The drug stays separate. */
  title: string | null;
  /** Set when this cycle runs content built for an earlier programme. */
  reuses?: string | null;
  state: ProgrammeState;
  starts_on: string | null;
  due_on: string | null;
  days_remaining: number | null;
  published_at: string | null;
  published_by: string | null;
  overrides: number;
  archived: { at: string; by_id: string; by_name: string; note: string } | null;
  cohort: { assigned: number; started: number; certified: number; average_uplift: number | null };
};

export type Client = { id: string; name: string; region: string; jurisdiction: string; curriculum: string };

export type ClientProgrammes = {
  client: Client;
  programmes: Programme[];
  states: Record<ProgrammeState, number>;
};

/** Consolidated across every programme a client ran. Averages are pooled over
 *  learners, never averaged over programmes. */
export type Portfolio = {
  client: Client;
  states: Record<ProgrammeState, number>;
  programmes: {
    run_id: string;
    drug: string;
    state: ProgrammeState;
    assigned: number;
    certified: number;
    average_uplift: number | null;
    days_to_publish: number | null;
    cost_saved_usd: number | null;
    /** Null when this cycle reuses content built for an earlier programme. */
    findings: number | null;
    overrides: number;
    reuses?: string | null;
  }[];
  reach: { assigned: number; started: number; certified: number; measured: number; certification_percent: number | null };
  uplift: { learners: number; baseline: number | null; final: number | null; points: number | null };
  speed: { median_days_to_publish: number | null; manual_days: number; programmes: number };
  cost: { build_usd: number; manual_usd: number; saved_usd: number; per_certified_usd: number | null; manual_per_certified_usd: number | null };
  governance: {
    findings: number;
    blocking_found: number;
    raised_to_reviewers: number;
    settled: number;
    agreement_percent: number | null;
    overrides: number;
    coverage_percent: number | null;
  };
};

export type JourneyStep = {
  id: string;
  title: string;
  detail: string;
  state: "done" | "current" | "waiting";
  evidence: string[];
  href: string;
};

/** The ten steps a programme goes through. Computed from the record, never stored. */
export type Journey = {
  run_id: string;
  steps: JourneyStep[];
  done: number;
  total: number;
  percent: number;
  state: ProgrammeState;
};

export type Evidence = {
  citation: { title: string; url: string; locator: string; supporting_text: string };
  claim: { text: string; evidence_type: string; section_id: string; section_title: string };
  related: { text: string; section_title: string }[];
  supports_claims: number;
};

export type Knowledge = {
  drug: Drug;
  title: string;
  gaps: string[];
  warnings: string[];
  sources: SourceList["sources"];
  sections: { id: string; title: string; summary: string; gaps: string[]; warnings: string[]; claims: { text: string; evidence_type: string; citations: Citation[] }[] }[];
};

export type StagedSource = { id: string; kind: "upload" | "web"; name: string; note: string; bytes?: number; content_type?: string; added_at: string; status: string; title?: string; http_status?: number; error?: string };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, { cache: "no-store", ...init });
  if (!response.ok) {
    const body = await response.text();
    let detail = body;
    try { detail = JSON.parse(body).detail ?? body; } catch { /* plain-text error */ }
    throw new Error(detail || response.statusText);
  }
  return response.json();
}

export function getJson<T>(path: string): Promise<T> {
  return request<T>(path);
}

export function sendJson<T>(path: string, body: unknown, method: "POST" | "PATCH" = "POST"): Promise<T> {
  return request<T>(path, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

export function sendForm<T>(path: string, body: FormData): Promise<T> {
  return request<T>(path, { method: "POST", body });
}
