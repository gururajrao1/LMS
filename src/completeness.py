"""Whether the course covers what a knowledgeable reader would expect.

`judge` asks whether what the course says is true. This asks whether anything
required is missing, which fails differently and needs its own mechanism: a course
can be entirely accurate and still be dangerous because it never mentions a
contraindication, and no amount of quote-checking will notice.

The required topics are declared in `config/curriculum/*.toml`, not here, so a
medical education lead can change what "complete" means without touching code.

Deliberately a coverage signal, not a quality score. Matching a topic means the
course addresses it *at all*; whether it addresses it *well* is a judgement, and
judgements belong to the reviewer. That is why a gap becomes a review comment in
the ordinary queue rather than a number on a dashboard.
"""

import tomllib
from pathlib import Path

from src import judge
from src.agent import ROOT, content_path

CURRICULA = ROOT / "config" / "curriculum"
DEFAULT_CURRICULUM = "us_oncology"

# A gap is the checker's finding like any other, so it wears the same identity and
# goes through the same address/dismiss flow a human comment does.
TARGET_FOR_SEVERITY = {"blocking": "sources", "major": "sources", "minor": "sources"}


def curriculum(name: str = DEFAULT_CURRICULUM) -> dict:
    path = CURRICULA / f"{Path(name).name}.toml"
    if not path.exists():
        raise ValueError(f"No curriculum named {name}")
    return tomllib.loads(path.read_text())


def _covered_by(topic: dict, units: list[dict]) -> list[dict]:
    """Every unit that addresses this topic, in the order a reader meets them."""
    patterns = [pattern.lower() for pattern in topic["patterns"]]
    hits = []
    for unit in units:
        text = f"{unit['reference']} {unit['text']}".lower()
        matched = [pattern for pattern in patterns if pattern in text]
        if matched:
            hits.append({"id": unit["id"], "reference": unit["reference"],
                         "asset": unit["asset"], "matched": matched})
    return hits


# A single passing mention is not coverage. Saying so is the difference between a
# matrix that reports and one that flatters — and "mentioned once" is exactly the
# state a reviewer most needs pointed out, because it reads as covered otherwise.
STATES = ("missing", "thin", "covered")


def _state(hits: int, minimum: int) -> str:
    if not hits:
        return "missing"
    return "thin" if hits < minimum else "covered"


def matrix(run_id: str, tracks=("hcp", "msl"), name: str = DEFAULT_CURRICULUM) -> dict:
    """Required topic against what each track actually covers."""
    spec = curriculum(name)
    rows = []
    for topic in spec["topic"]:
        minimum = topic.get("min_units", 2)
        row = {
            "id": topic["id"],
            "title": topic["title"],
            "why": topic["why"],
            "severity": topic["severity"],
            "min_units": minimum,
            "tracks": {},
        }
        for track in tracks:
            if track not in topic["audiences"]:
                row["tracks"][track] = None  # not required of this audience
                continue
            hits = _covered_by(topic, judge.units(run_id, track))
            row["tracks"][track] = {
                "state": _state(len(hits), minimum),
                "units": hits[:4],
                "total": len(hits),
            }
        rows.append(row)

    cells = [(row, track, cell) for row in rows for track, cell in row["tracks"].items() if cell]
    counted = {state: sum(1 for _, _, cell in cells if cell["state"] == state) for state in STATES}
    return {
        "run_id": run_id,
        "curriculum": {"name": spec["name"], "jurisdiction": spec.get("jurisdiction", ""),
                       "reviewed_on": spec.get("reviewed_on", ""), "topics": len(spec["topic"])},
        "tracks": list(tracks),
        "rows": rows,
        "stats": {
            "required": len(cells),
            **counted,
            "percent": round(100 * counted["covered"] / len(cells)) if cells else 100,
            "missing_blocking": sum(1 for row, _, cell in cells
                                    if cell["state"] == "missing" and row["severity"] == "blocking"),
        },
    }


def gap_id(track: str, topic_id: str) -> str:
    """Stable across re-runs, so a gap already raised is never raised twice."""
    return f"completeness:{track}:{topic_id}"


def gaps(run_id: str, tracks=("hcp", "msl"), name: str = DEFAULT_CURRICULUM) -> list[dict]:
    """Every required topic a track does not properly cover, worst first.

    A topic mentioned once is raised a severity lower than one never mentioned:
    still worth a reviewer's attention, but it is a thinness problem rather than
    an absence.
    """
    order = {"blocking": 0, "major": 1, "minor": 2}
    softer = {"blocking": "major", "major": "minor", "minor": "minor"}
    found = [
        {
            "finding_id": gap_id(track, row["id"]),
            "track": track,
            "topic": row["id"],
            "title": row["title"],
            "why": row["why"],
            "state": cell["state"],
            "units": cell["total"],
            "expected": row["min_units"],
            "severity": row["severity"] if cell["state"] == "missing" else softer[row["severity"]],
        }
        for row in matrix(run_id, tracks, name)["rows"]
        for track, cell in row["tracks"].items()
        if cell and cell["state"] != "covered"
    ]
    return sorted(found, key=lambda gap: (order.get(gap["severity"], 3), gap["track"]))


def promote(run_id: str, finding_ids: list[str] | None = None,
            tracks=("hcp", "msl"), name: str = DEFAULT_CURRICULUM) -> list[dict]:
    """Raise coverage gaps into the ordinary review queue.

    Mirrors `judge.promote`: the checker authors the comment, an expert addresses
    or dismisses it, and re-running never duplicates one already raised.
    """
    from src import learning

    record = learning.course(run_id)
    already = {comment.get("finding_id") for comment in record["comments"] if comment.get("finding_id")}
    wanted = set(finding_ids or [])
    raised = []
    for gap in gaps(run_id, tracks, name):
        if (wanted and gap["finding_id"] not in wanted) or gap["finding_id"] in already:
            continue
        body = (
            f"{gap['title']} is not covered anywhere in the {gap['track'].upper()} track.\n{gap['why']}"
            if gap["state"] == "missing" else
            f"{gap['title']} is mentioned in only {gap['units']} unit of the {gap['track'].upper()} "
            f"track, below the {gap['expected']} this curriculum expects. It reads as covered but is "
            f"not.\n{gap['why']}")
        comment = learning.add_comment(
            run_id, learning.CHECKER["id"], TARGET_FOR_SEVERITY.get(gap["severity"], "sources"),
            gap["severity"], body)
        record = learning.course(run_id)
        stored = next(entry for entry in record["comments"] if entry["id"] == comment["id"])
        stored["finding_id"] = gap["finding_id"]
        stored["origin"] = "automated_check"
        stored["check"] = "not_covered"
        learning._save_course(record)
        already.add(gap["finding_id"])
        raised.append(stored)
    return raised


def report_path(run_id: str) -> Path:
    return content_path("platform", "completeness", f"{Path(run_id).name}.json")
