# Figure questions

Questions asked about a chart the learner has to read. The chart is rendered from the numbers you return, so those numbers are learner-facing clinical content and are held to exactly the same standard as any other claim: every value must come from the evidence recorded in the dossier, and each question carries the citation it came from.

Return `title` and 3–4 `questions`.

Each question needs `id`, `caption`, `chart_kind`, `x_title`, `y_title`, `y_suffix`, `series`, `prompt`, `options`, `correct_index`, `rationale` and `citations`.

- `id` must be unique and must not be of the form `q1`, `q2`, … — prefix it, for example `f1`.
- `caption` says in one line what the chart shows, including the population and the study or label section it is drawn from.
- `chart_kind` is `line` for something measured over time and `bar` for a comparison between named groups.
- `x_title` and `y_title` name the axes. `y_suffix` is the unit shown after each value — `"%"`, `" mo"`, or an empty string.
- `series` is 1–2 named series. Two only when the comparison is the point, and then name them as a reader would need to see them, for example "Palbociclib + letrozole" and "Letrozole alone". Each series has `points`, and every series must use the same `label` values in the same order.
- `points` is 3–8 entries of `label` and `value`. For a line chart the labels are time points in order.
- `prompt` asks something that can only be answered by reading the chart — a difference, a crossing, a value at a point, a trend.
- `options` is an object with exactly four fields `a`, `b`, `c`, `d`; `correct_index` is 0 for `a`, 1 for `b`, 2 for `c`, 3 for `d`.
- `rationale` explains the answer in terms of what the chart shows, and states the figure it is read from.

Rules:

- **Never invent a number.** If the dossier does not record a value, do not plot it. A chart is read as data and a plausible-looking invented curve is the worst thing this system could produce. Prefer three real points over eight smooth ones.
- Do not describe photographs, scans, histology or any image of a patient. The only figure is the chart built from these numbers.
- If the recorded evidence gives a median and a hazard ratio but not a curve, use a `bar` chart of the medians rather than drawing a survival curve you do not have.
- Every wrong option must be a number or reading that is wrong *for this chart* — a misread of the other series, the wrong time point, a plausible transposition.
- The audience is expert. Do not ask which bar is taller; ask what the difference means.
