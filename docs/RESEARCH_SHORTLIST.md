# Research shortlist, round 2 — evidence-backed features for PharmaLearn

Source: deep-research pass over the full app, research papers (arXiv),
peer-reviewed journals (PMC), and enterprise/pharma LMS vendor evidence
(Nov 2026). Each item names its evidence so a reviewer can check it.
Related prior notes: [RESEARCH_README](../RESEARCH_README.md) (patterns),
[FEATURE_SHORTLIST](../FEATURE_SHORTLIST.md) (statuses), [FUTURE_FEATURES](FUTURE_FEATURES.md) (parked).

Status key: NEW = not in the app or shortlist yet. EXTENDS = upgrades an
existing item. CONFIRMED = already shortlisted, now source-backed.

## A. Citation and verification pipeline (new builds)

### 1. Double-pass retrieval-citation — NEW
MedCite (arXiv 2506.06605, ACL 2025 Findings): non-parametric retrieval
first, then post-generation re-retrieval + LLM reranking + dedup beats
LLM self-citation (which fabricates or mangles citations) by up to
+47% citation recall / +32% precision, correlating with doctor judgments.
Build: keep the current RAG pre-pass, add a post-generation pass that
re-retrieves per claim, reranks, and dedups before the checker sees it.

### 2. Sentence-level citation F1 checker — NEW
LongCite / LongBench-Cite (arXiv 2409.02897): automated citation
recall/precision/F1 judged per sentence, tracking citation length so
coarse paragraph-citations can't inflate scores; SFT on such data also
reduces hallucinations. Build: extend the current `quote_spans` /
`quote_match` checks with per-sentence F1 plus a granularity metric.

### 3. Ablation self-check reranker — NEW
SelfCite (arXiv 2502.09604): necessity (answer breaks when cited text is
removed) + sufficiency (answer holds on cited text alone) as a
self-supervised filter, ~+5 F1 via best-of-N/SimPO. Build: run the
ablation test as a reranker over candidate cited answers before serving.

### 4. Adaptive retrieval gating with critique — NEW
Self-RAG (arXiv 2310.11511): retrieve only when needed, critique each
segment with relevance/support/utility tokens, keep support-scored
segments; 7B/13B models beat ChatGPT on factuality and citation
accuracy. Build: gate dossier retrieval per question and score kept
segments, instead of always retrieving top-k.

### 5. Refusal-on-zero-support gate — NEW (design, not paper-backed)
None of the four citation papers implement abstention; all lack a
refusal mechanism. Design it: emit an explicit refusal/escalation when
citation recall is 0 or no span entails the statement, rather than a
hedged answer. Pairs with the existing dismissal-challenge ethos.

## B. Learning assets and analytics (new builds)

### 6. PEER-grounded question generation asset — NEW
PaniniQA (TACL 2023, arXiv 2308.03253): extract salient clinical
events/relations, then Prompt → Evaluate → Expand → Repeat turns with
answer verification and timely correction of misunderstandings. Build:
a discharge-note-style interactive QA asset reusing the triage/assemble
patterns, with expand/repeat feedback turns.

### 7. Rationale-citing verifier asset — NEW
SciFact (EMNLP 2020, arXiv 2004.14974): retrieve abstracts, select
rationale sentences, then verdict (Supports/Refutes) — 1.4K
expert-written claims with rationales. Build: a verifier asset that
shows its rationale sentences alongside each verdict, for reviewer and
learner trust.

### 8. Claim-level evidence-F1 impact metrics — NEW
FEVER (NAACL 2018, arXiv 1803.05355): 185K claims labeled
Supported/Refuted/NotEnoughInfo with evidence sentences; report
label accuracy *with* correct evidence, not label-only. Build: Impact
tab reports verification accuracy conditioned on evidence quality.

### 9. Leakage-free mastery-over-time analytics — EXTENDS skills-gap item
pyKT (NeurIPS Datasets & Benchmarks 2022, arXiv 2206.11460):
standardized preprocessing + 10 knowledge-tracing implementations,
with the warning that wrong eval settings leak labels and inflate AUC.
Build: mastery curves per skill with pyKT-style leakage-free eval, so
the hardest-questions rollup can't fool itself.

### 10. Hierarchical interaction mining — NEW
EdNet (AIED 2020, 131M interactions, 784K learners): question-solving,
lecture consumption, and purchase actions in one hierarchy. Build: mine
the existing attempt/feedback/module-engagement hierarchy to find
content gaps (which material precedes which failures), feeding the next
version's fix list.

## C. Learning-science corrections (design changes)

### 11. Decay-aware spaced scheduling + delayed retention metric — EXTENDS spaced reinforcement
DAS3H (Papers With Code): knowledge tracing with memory decay +
multi-skill tagging to schedule distributed practice. Cureus 2026
systematic review: spaced retrieval works, benefits grow with
sustained longitudinal engagement; self-directed flashcard evidence is
weak (selection bias). Anki review (Med Sci Educ 2026): associations
are observational, not causal. And exam scores ≠ retention unless
measured after a defined interval. Build: schedule re-quiz by decay +
skill tags, and measure retention at a fixed delay — baseline→final
uplift alone doesn't prove retention.

### 12. Depth metrics for the Ask bot — EXTENDS chatbot
Lenny AI randomised crossover trial (Behav Sci 2025, n=20): chatbots
win on ease/satisfaction/engagement but show *no* performance gain —
fast System-1 recall without System-2 depth; students asked for source
references. The app already answers with citations; add depth metrics
(follow-up correctness, rationale quality) so engagement can't masquerade
as learning.

### 13. AI video stays adjunct-only — CONFIRMED parked decision
BMJ Open Qual 2025 systematic review: 5 of 103 studies eligible,
controls beat AI video on accuracy (p<0.005), plus bias/rendering
errors. Keep MOA animation as storyboard-first (already parked in
FUTURE_FEATURES.md); require non-inferiority evidence before any
generative-video build.

## D. Already shortlisted, now source-backed (no new design needed)

- **Part 11 e-signatures** (meaning + credential re-auth), **immutable
  audit trail + inspector-ready reports**, **validation pack** (GAMP 5 /
  IQ/OQ): Veeva Vault Training, ComplianceWire/ULTRUS, MasterControl
  vendor evidence; buyer guides rate generic LMS (Cornerstone, Docebo,
  Absorb) single-check on audit trails vs double-check for GxP-native.
- **SOP/label-change auto re-enrollment**: Vault QualityDocs→QMS→Training
  closed loop (CAPA/revision triggers retraining).
- **Rules-engine auto-enrollment, scheduled emailed reports, SSO/SCIM +
  HRIS sync, multilingual tracks, manager rollups, skills-gap rollups +
  auto-paths**: Docebo/Absorb/TalentLMS/Cornerstone vendor evidence
  (all pages fetched 200); prioritize in that order for enterprise demos.

## E. Follow-up pass closed two gaps (Nov 7)

### 14. Course-criticality RAG rollup — EXTENDS noncompliance RAG tiers
The first pass found no literal red/amber/green course scheme; targeted
search did. Access LMS Evo uses RAG per mandatory-training category
(amber by default within 4 months of certificate expiry); LifeSafety.ai
defines red as critical gaps needing immediate action, amber as
approaching deadlines, green as compliant; Skillcast assigns RAG ratings
to responses; CareShield/Myrus reports compliance in RAG throughout.
See [Access Evo compliance apps](https://help-accesslmsevo.theaccessgroup.com/en/articles/17264905-compliance-apps),
[LifeSafety dashboard](https://www.lifesafety.ai/risk-management-dashboard/).
Build: roll the existing per-learner RAG tiers up to a per-course /
per-cohort RAG (red = anyone overdue or below pass mark, amber = due or
expiring within the window, green = all complete) on the Cohort tab and
portfolio. No invention needed — thresholds mirror the vendors'.

### 15. Semantic short-answer grading — NEW
Current scoring is multiple-choice only (`correct_index`, server-side).
EvalAI (BJCNIT 2026) grades theory answers by Sentence-BERT similarity
to a reference answer: Pearson 0.81, MAE 0.18 against Mohler's
human-graded benchmark. EDM 2021 shows SBERT grading generalizes to
out-of-sample questions; EvaluAI (SoftwareX, Apache-2.0, self-hostable)
does the same with LLMs plus instructor review. See
[EvalAI paper](https://abjournals.org/bjcnit/9/2/design-and-implementation-of-a-sentence-bert-driven-semantic-matching-model-for-automated-evaluation-of-theory-answers-200.pdf),
[EDM21 SBERT paper](https://educationaldatamining.org/EDM2021/virtual/static/pdf/EDM21_paper_149.pdf).
Build: optional free-text questions on baseline/final, scored by
similarity to the recorded reference answer with a human-review threshold
(low-confidence scores route to a reviewer, never auto-fail) — consistent
with the dismissal-challenge ethos. Lightweight path first: embedding
similarity only; LLM adjudication only for the review queue.
