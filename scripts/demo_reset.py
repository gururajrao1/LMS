"""Remove the runs a demo or rehearsal generated, leaving the seeded ones alone.

Every rehearsal of Act 1 creates a new `ibrance-<timestamp>` run with its own
content, log, checks report and course record. None of it is wanted afterwards,
and none of it should be cleared by hand at 9am on the day.

Only timestamped runs are touched. The bundled first run and the seeded cycles
are what the demo is built on, so they are never candidates — passing `--all`
does not widen this, and there is no flag that does.

    uv run python scripts/demo_reset.py            # show what would go
    uv run python scripts/demo_reset.py --yes      # remove it
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent import content_path  # noqa: E402

# A generated run is the drug slug and a UTC stamp. `ibrance-cycle-*` and the
# original bundled run do not match, which is the whole protection.
GENERATED = re.compile(r"^[a-z0-9-]+-\d{8}T\d{6,}Z$")
KEEP = {"ibrance-20260715T084025801360Z"}


def candidates() -> list[str]:
    root = content_path("content")
    found = {path.name for path in root.iterdir() if path.is_dir()} if root.exists() else set()
    logs = content_path("logs")
    if logs.exists():
        found |= {path.name for path in logs.iterdir() if path.is_dir()}
    return sorted(name for name in found if GENERATED.match(name) and name not in KEEP)


def remove(run_id: str) -> None:
    for path in [content_path("content", run_id),
                 content_path("logs", run_id),
                 content_path("platform", "progress", run_id)]:
        shutil.rmtree(path, ignore_errors=True)
    for path in [content_path("platform", "courses", f"{run_id}.json"),
                 content_path("platform", "checks", f"{run_id}.json")]:
        path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="actually remove them")
    args = parser.parse_args()

    runs = candidates()
    if not runs:
        print("Nothing to reset — no generated runs on disk.")
        return
    for run_id in runs:
        print(f"  {'removing' if args.yes else 'would remove'} {run_id}")
        if args.yes:
            remove(run_id)
    print(f"{len(runs)} run(s) {'removed' if args.yes else 'listed'}. "
          f"{'' if args.yes else 'Re-run with --yes to remove them.'}")


if __name__ == "__main__":
    main()
