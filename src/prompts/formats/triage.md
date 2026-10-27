# Triage board

A sort board: the learner is shown short clinical findings one at a time and drops each into one of two buckets. It is scored as an assessment, so every item must have exactly one defensible answer that the label or trial evidence settles.

Return `title`, `instruction`, `buckets` and 6–8 `items`.

`buckets` is an object with exactly two fields, `a` and `b`, each a short bucket label of at most six words naming an **action or a decision** — what the reader would do. Prefer labels a clinician acts on ("Hold the dose and recheck", "Continue at the current dose") over labels that only name a category ("Severe", "Not severe").

`instruction` is one sentence telling the learner what question they are answering for each item.

Each item needs `id`, `prompt`, `correct_index`, `rationale` and `citations`.

- `id` must be unique and must not be of the form `q1`, `q2`, … — prefix it, for example `t1`.
- `prompt` is the thing being sorted: a specific clinical finding, grade, lab value or scenario in at most 20 words. No question mark, no options listed — the buckets are the options.
- `correct_index` is 0 for bucket `a` or 1 for bucket `b`.
- `rationale` explains in one or two sentences why the labelled action follows, in the terms the source uses.
- `citations` are the one or two strongest sources for that item, exactly as for quiz questions.

Rules:

- Every item must be settled by the cited evidence. If the correct bucket depends on clinical judgement the source does not resolve, do not include the item.
- Both buckets must be used, and neither may hold fewer than two items — a board where one bucket is almost always right teaches the shortcut rather than the content.
- **The board must defeat the surface reading.** A reader who ignores the content and sorts on severity alone — anything reading serious or high-grade into the first bucket, anything reading mild or low-grade into the second — must score below half. At least one item in three has to be one where that reading gives the *wrong* bucket: a serious-sounding finding the label says to continue through, or a mild-sounding one it says to act on. A board that rewards the shortcut teaches the shortcut.
- Items must be discriminating: include at least two that a reader would get wrong from general oncology knowledge alone and only get right from this drug's label, such as a threshold or a timing that differs from the class norm.
- Do not restate the bucket inside the prompt, and do not use the bucket's own words in the item.
- The audience is expert. Grade the findings, name the values, use the units the label uses.
