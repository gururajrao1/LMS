# Assembled instruction

Word building, in the form that matters clinically: the learner rebuilds a labelled instruction by choosing the phrase that goes in each slot. The words being chosen are the ones that change what a clinician would do — a threshold, a timing, a dose, a duration — never a synonym or a spelling.

Return `title`, `instruction` and 3–4 `items`.

`instruction` is one sentence telling the learner what they are building.

Each item needs `id`, `prompt`, `blanks`, `tail`, `rationale` and `citations`.

- `id` must be unique and must not be of the form `q1`, `q2`, … — prefix it, for example `a1`.
- `prompt` names the situation the instruction applies to, in at most 15 words. For example: "Grade 3 neutropenia found on Day 1 of a cycle".
- `blanks` is a list of 2–3 slots, in reading order. Each has its own `id` (unique across the whole asset, for example `a1-b1`), a `before` string, `options` and `correct_index`.
  - `before` is the fixed text that comes immediately before that slot, including any leading space. For the first blank this is the opening of the sentence; it may be an empty string if the sentence starts with a slot.
  - `options` is an object with exactly four fields `a`, `b`, `c`, `d` — four candidate phrases for that slot. `correct_index` is 0 for `a`, 1 for `b`, 2 for `c`, 3 for `d`.
- `tail` is the fixed text after the last slot, including the full stop. It may be an empty string.
- `rationale` explains in one or two sentences why the completed instruction is what the label says.
- `citations` are the one or two strongest sources, exactly as for quiz questions.

Rules:

- Reading the assembled sentence with the correct phrase in every slot must produce exactly what the label directs — not a paraphrase of it.
- Every wrong option must be **plausible and specific**: a different threshold, a different timing, a different dose. Never a nonsense phrase, never a grammatical mismatch, and never an option a reader can eliminate without knowing the label.
- Do not put the answer to one slot inside the fixed text of another.
- Slots must be independently decidable. A reader who gets the first slot wrong must still be able to get the second one right.
- The audience is expert. Use the label's own units and terms.
