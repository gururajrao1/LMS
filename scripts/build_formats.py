"""Generate the gamified assessment formats for a run's tracks, from its dossier.

Three formats, each an asset like any other — one agent call per format per track
against the master dossier the rest of the course was built from, returning items
that carry their own citations:

    triage    a sort board: one finding at a time into one of two action buckets
    assemble  word building: a labelled instruction rebuilt from phrase chips
    figure    read-the-data questions about a chart drawn from cited numbers

Each is written on its own, as the agent authored it and as a reviewer reads it,
and folded into `quiz.json` where every item becomes an ordinary scored question
(see `agent.fold_groups`). Nothing downstream needs to know a game was played.

Existing runs are not modified unless `--fold` names one, and folding refuses to
run twice over the same quiz because item ids would collide.

    uv run python scripts/build_formats.py --dry-run              # what it would cost
    uv run python scripts/build_formats.py                        # write to the library
    uv run python scripts/build_formats.py --format figure        # just one format
    uv run python scripts/build_formats.py --fold RUN_ID          # and into that run's quiz
"""

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import agent  # noqa: E402
from src.agent import DATA, content_path  # noqa: E402

TRACKS = ("hcp", "msl")

# What a learner who reads nothing but the adjectives would do: put anything that
# sounds serious in the acting bucket and everything else in the continuing one.
SEVERE = re.compile(r"grade 3|grade 4|severe|serious|worsening|recurrent|suspicious|suspected|life-threatening", re.I)
ACTING = re.compile(r"hold|withhold|interrupt|reduce|modify|adjust|stop|discontinue|delay|act", re.I)


def acting_bucket(board: dict) -> int:
    """Which bucket means "do something". The agent picks the order, not us.

    Assuming bucket 0 was the acting one measured the *inverse* heuristic on any
    board that happened to list "continue" first, and reported a number that
    looked plausible either way — the kind of wrong that survives review because
    nothing about it looks broken.
    """
    labels = [board["buckets"][key] for key in ("a", "b")] if isinstance(board["buckets"], dict) \
        else list(board["buckets"])
    return 0 if ACTING.search(labels[0]) and not ACTING.search(labels[1]) else 1


def shortcut_score(board: dict) -> int:
    """What a reader sorting on adjectives alone scores.

    A smoke alarm, not a grade. It knows the words in SEVERE and nothing else, so
    it cannot see that "Child-Pugh class B" or "CrCl 25 mL/min" are severity cues
    to a clinician — it will score those items as shortcut-proof when they are
    only regex-proof. Tuning a board until this number falls would be teaching to
    a test written by a regex.

    What it does catch is the failure worth catching: a board built entirely out
    of "Grade 3 → act, Grade 1 → continue" pairs, which measures vocabulary. The
    first board generated here scored 86% and was exactly that.
    """
    items, acting = board["items"], acting_bucket(board)
    hits = sum((acting if SEVERE.search(item["prompt"]) else 1 - acting) == item["correct_index"]
               for item in items)
    return round(100 * hits / len(items)) if items else 0


def _library(drug: str) -> Path:
    return DATA / "library" / drug


SHORTCUT_LIMIT = 50


async def _board(master: dict, track: str, budget: agent.RunBudget) -> dict:
    """Generate a board, measure it, and regenerate once if the shortcut passes it.

    The model does not reliably comply with "make it shortcut-proof" stated as a
    rule — asked for one item in three that defeats the surface reading, it
    produced one in eight. It complies when it is shown the measurement, so the
    number goes back into the prompt rather than into a warning nobody reads.

    One retry only. This is a bounded correction, not a loop that spends until it
    gets lucky, and the second board is kept only if it is genuinely better.
    """
    board = await agent._asset(master, track, "triage", None, budget)
    score = shortcut_score(board)
    if score <= SHORTCUT_LIMIT:
        return board

    print(f"  … {track}: surface reading scores {score}% — regenerating with the measurement")
    acting = acting_bucket(board)
    guessable = [item["prompt"] for item in board["items"]
                 if (acting if SEVERE.search(item["prompt"]) else 1 - acting) == item["correct_index"]]
    retry = await agent._asset(master, track, "triage", None, budget, note="\n\n".join([
        f"MEASUREMENT OF YOUR PREVIOUS BOARD: a reader who ignored the content and sorted on severity "
        f"wording alone — anything reading serious or high-grade into the first bucket, everything else "
        f"into the second — scored {score}%. The pass mark for this assessment is around 70%, so that "
        f"reader would have passed without knowing the label.",
        "These items rewarded that reader:\n" + "\n".join(f"  - {prompt}" for prompt in guessable),
        f"Rebuild the board so the same reader scores below {SHORTCUT_LIMIT}%. Keep the items that "
        "already defeat it. Replace the rest with findings where the labelled action runs against the "
        "surface reading: serious-sounding findings this label says to continue through, and mild or "
        "unremarkable-sounding ones it says to act on. Every item must still be settled by its citation.",
    ]))
    improved = shortcut_score(retry)
    if improved >= score:
        print(f"  … {track}: retry scored {improved}% — keeping the first board")
        return board
    return retry


PLACEHOLDER = re.compile(r"^(placeholder|tbd|todo|n/?a|example|lorem)\b", re.I)


def unusable(kind: str, item: dict) -> str:
    """Why this item cannot be shipped, or an empty string if it can.

    Generation degrades rather than failing: asked not to invent numbers, the
    model twice returned a well-formed question whose prompt was the literal word
    "placeholder" and whose citations were empty. The JSON validated, so nothing
    upstream objected — a chart would have rendered under the question
    "placeholder". Cheap to detect, embarrassing to demo.
    """
    prompt = (item.get("prompt") or "").strip()
    if not prompt or PLACEHOLDER.match(prompt):
        return f"prompt is {prompt or 'empty'!r}"
    if len(prompt) < 15:
        return f"prompt is too short to be a question ({prompt!r})"
    if not item.get("citations"):
        return "no citations, so the checker would block it anyway"
    if kind == "figure":
        points = [len(series["points"]) for series in item.get("series", [])]
        if not points or min(points) < 2:
            return "fewer than two plotted points"
    return ""


def keep_usable(kind: str, track: str, asset: dict) -> dict:
    """Drop what cannot ship, and say exactly what went and why."""
    field = "questions" if kind == "figure" else "items"
    kept = []
    for item in asset.get(field, []):
        reason = unusable(kind, item) if kind == "figure" else ""
        if reason:
            print(f"  ! {track} {kind}: dropped {item.get('id', '?')} — {reason}")
        else:
            kept.append(item)
    return {**asset, field: kept}


def _report(kind: str, track: str, asset: dict) -> None:
    """Say what was built and what is wrong with it, before anyone sees it."""
    items = asset["items"] if kind != "figure" else asset["questions"]
    if kind == "triage":
        acting = acting_bucket(asset)
        counts = [sum(item["correct_index"] == index for item in items) for index in (acting, 1 - acting)]
        shortcut = shortcut_score(asset)
        print(f"+ {track} triage: {len(items)} items, {counts[0]} act / {counts[1]} continue, "
              f"surface reading scores {shortcut}%")
        if min(counts) < 2:
            print(f"  ! {track}: a bucket holds fewer than two items — the board is not discriminating")
        if shortcut > 75:
            print(f"  ! {track}: sorting on severity words alone scores {shortcut}% — this is a vocabulary test")
    elif kind == "assemble":
        blanks = sum(len(item["blanks"]) for item in items)
        print(f"+ {track} assemble: {len(items)} instructions, {blanks} slots")
        for item in items:
            for blank in item["blanks"]:
                if len({value for value in blank["options"].values()}) < 4:
                    print(f"  ! {track}: slot {blank['id']} repeats an option — one of them cannot be wrong")
    else:
        points = sum(len(series["points"]) for item in items for series in item["series"])
        print(f"+ {track} figure: {len(items)} charts, {points} plotted values")
        for item in items:
            lengths = {len(series["points"]) for series in item["series"]}
            if len(lengths) > 1:
                print(f"  ! {track}: {item['id']} has series of different lengths — the chart will misalign")

    missing = [item["id"] for item in items if not item.get("citations")]
    if missing:
        print(f"  ! {track}: uncited {kind} items {', '.join(missing)} — the checker will raise these")


async def _usable_asset(master: dict, track: str, kind: str, budget: agent.RunBudget) -> dict:
    """Generate, drop what cannot ship, and ask again once if that emptied it out.

    Told what was rejected and why, rather than told the rule again — the same
    correction that worked on the sort board. One retry, and the better of the
    two is kept, so a bad second attempt cannot lose a usable first one.
    """
    field = "questions" if kind == "figure" else "items"
    raw = await agent._asset(master, track, kind, None, budget)
    first = keep_usable(kind, track, raw)
    dropped = len(raw[field]) - len(first[field])
    if not dropped:
        return first

    print(f"  … {track} {kind}: {dropped} item(s) unusable — asking again with the reason")
    retry = keep_usable(kind, track, await agent._asset(master, track, kind, None, budget, note="\n\n".join([
        f"YOUR PREVIOUS RESPONSE WAS PARTLY UNUSABLE: {dropped} item(s) were discarded because the "
        "prompt was a placeholder or the citations were empty. An item without a real question and a "
        "real citation cannot be shown to a learner and would be blocked by the content checker.",
        "Return only items you can fully complete from the recorded evidence. Fewer complete items is "
        "the right answer — three fully cited questions beat six with gaps. Never emit the word "
        "'placeholder', and never return an item with an empty citations list.",
    ])))
    return retry if len(retry[field]) > len(first[field]) else first


async def build(run_id: str, drug: str, kinds: list[str], tracks: tuple[str, ...], fold_into: str | None, dry_run: bool) -> int:
    master = json.loads(content_path("content", run_id, "context.json").read_text())
    budget = agent.RunBudget(run_id)
    print(f"Dossier: {master['drug']['brand']} · spent so far ${budget.spent_usd:.2f} of ${budget.limit_usd:.2f}")
    if dry_run:
        print(f"Would generate {', '.join(kinds)} for {len(tracks)} track(s) — "
              f"{len(kinds) * len(tracks)} call(s) against the stored dossier.")
        return 0

    for track in tracks:
        groups, figures = [], []
        for kind in kinds:
            if kind == "triage":
                asset = keep_usable(kind, track, await _board(master, track, budget))
            else:
                asset = await _usable_asset(master, track, kind, budget)
            if not (asset.get("questions") if kind == "figure" else asset.get("items")):
                print(f"  ! {track}: no usable {kind} items — the format is skipped for this track")
                continue
            target = _library(drug) / track / f"{kind}.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(asset, indent=2) + "\n")
            _report(kind, track, asset)
            if agent.GAMIFIED[kind]:
                groups.append({"id": agent._slug(asset["title"])[:40], "kind": agent.GAMIFIED[kind], **asset})
            else:
                figures += asset["questions"]

        if fold_into:
            quiz_path = content_path("content", fold_into, track, "quiz.json")
            folded = agent.fold_groups(json.loads(quiz_path.read_text()), groups, figures)
            quiz_path.write_text(json.dumps(folded, indent=2) + "\n")
            for kind in kinds:
                (quiz_path.parent / f"{kind}.json").write_text(
                    (_library(drug) / track / f"{kind}.json").read_text())
            print(f"  folded into {quiz_path} — {len(folded['questions'])} questions total")

    print(f"\nSpent ${budget.spent_usd:.2f} of ${budget.limit_usd:.2f}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", default="", help="run whose dossier the formats are built from")
    parser.add_argument("--drug", default="ibrance", help="library folder to write the formats into")
    parser.add_argument("--format", action="append", dest="formats", choices=sorted(agent.GAMIFIED),
                        help="build only this format (repeatable); default is all three")
    parser.add_argument("--fold", default="", help="also fold the formats into this run's quiz.json")
    parser.add_argument("--track", action="append", dest="tracks", choices=list(TRACKS),
                        help="build only this track (repeatable); default is both")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    run_id = args.run
    if not run_id:
        # A cycle reuses content it did not build, so its dossier is a symlink to
        # someone else's; building from it would charge the wrong run's budget.
        runs = sorted(
            path.name for path in (DATA / "content").iterdir()
            if (path / "context.json").exists()
            and not json.loads((path / "manifest.json").read_text()).get("reuses")
        )
        if not runs:
            raise SystemExit("No run with a dossier of its own to build from.")
        run_id = runs[-1]

    # Ordered as GAMIFIED declares them, so the fold is deterministic whatever
    # order the flags were typed in.
    wanted = set(args.formats or agent.GAMIFIED)
    kinds = [kind for kind in agent.GAMIFIED if kind in wanted]
    return asyncio.run(build(run_id, args.drug, kinds,
                                tuple(args.tracks or TRACKS), args.fold or None, args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
