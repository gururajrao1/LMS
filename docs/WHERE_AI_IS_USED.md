# Where AI is used in PharmaLearn

Every place an AI agent does work, in plain terms — and, just as importantly, the
places it is deliberately kept out.

---

## The agents

Building one course for one drug takes around **740 agent calls**, run in three
stages. Each row is a job, not a chatbot.

| Stage | Agent | What it does |
|---|---|---|
| **Research** | Section researcher (×14) | One agent per section of the dossier — disease background, mechanism, clinical evidence, label, safety, market context, unmet needs, and so on. Each searches published sources and returns claims **with the citation and the exact sentence it came from**. |
| | Dossier builder | Combines the fourteen researched sections into one master dossier, the single source everything else is written from. |
| **Authoring** | Deck writer (×2) | Writes the slide-by-slide clinical presentation, once for each audience (field medical, and healthcare professionals). |
| | Video storyboard writer (×2) | Scene-by-scene narration and on-screen text. |
| | FAQ writer (×2) | The questions a field team actually gets asked, with escalation guidance. |
| | Quiz writer (×2) | The knowledge check, with the rationale for every answer. |
| | Sort-board writer (×2) | The gamified triage exercise — sort a clinical finding into the action the label requires. |
| | Instruction-builder writer (×2) | The word-building exercise — rebuild a labelled instruction from candidate phrases. |
| | Figure writer (×2) | Read-the-data questions, with charts drawn from trial numbers the dossier recorded. |
| | Slide designer (×2) | Turns the deck into a finished, branded PowerPoint file. |
| **Checking** | Content checker | Reads the learner-facing content and judges whether it **overstates the evidence recorded behind it** — stronger claims than the source supports, missing qualifiers, breadth beyond the licensed use. |
| | Second-opinion checker | Re-examines the serious findings before any of them reach a human, so reviewers are not sent to look at noise. |
| **In use** | Course assistant | Answers questions from staff and trainees, using only the claims collected for that course, and shows its sources. |

Everything an agent writes carries its citations forward. Nothing reaches a
learner without a named human approving it.

---

## Where AI is deliberately *not* used

This is the shorter list, and the more important one.

| Not AI | Why it matters |
|---|---|
| **Quote verification** | Whether a quoted sentence really appears in the source document is settled by matching text against the stored file. No judgement, no model, no variability — the same answer every time. **Five of the seven blocking findings on our example course came from here.** |
| **Citation traceability** | Whether a citation points at a document we actually hold is a lookup, not an opinion. |
| **Coverage** | Whether the course covers the topics a curriculum requires is measured against a list a medical education lead can edit. |
| **Scores, uplift and certificates** | Marking, the before-and-after knowledge measurement, and who is certified are arithmetic on recorded answers. |
| **Schedules and programme status** | Live, completed, overdue — derived from the calendar and the cohort every time they are read, so a label can never be stale or wrong. |
| **Programme questions to the assistant** | "When does this open?", "How many are certified?" are read straight off the record and marked *From the record*. A model would be guessing at facts we already hold. |
| **Approval** | The checker raises findings. It can never clear one. Only a named human signs off, and overriding a failing check is recorded against their name. |

---

## The rules the agents work under

- **Evidence only.** An agent writing content is given the dossier and told to use
  nothing else. An agent answering a question is given the retrieved claims and
  told the same.
- **Everything is cited.** Content without a citation is flagged automatically.
- **Nothing self-approves.** The machine triages; a person decides.
- **Spend is capped and logged.** Every call is metered against a per-course
  budget, and repeated work is served from cache rather than re-billed.

---

## What this means for a reviewer

The agents do the reading, the drafting and the first pass of checking — the
volume work. What arrives at a human reviewer is a short queue of specific,
evidenced objections, each one clickable through to the claim, the quoted
sentence, and the stored source document itself.

*Figures in this note describe the Ibrance example course: 14 research sections,
341 citations, 109 findings raised by the checker, 7 of them blocking.*
