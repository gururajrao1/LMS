"""Backfill the pointer registry from existing snapshot manifests.

Every fetch run already wrote `.pharmalearn/sources/<drug>/<snapshot>/<source>/
manifest.json` with the source URL, identifiers, file hashes, access level, and
fetch time. This folds those manifests into one drug-level registry
(`sources/<drug>/registry.json`) so the checker can verify against recorded
text without the raw blobs. Idempotent: re-running changes nothing, because a
record only wins when its retrieval time is newer.

Readable text is copied from the snapshot's raw files (XML/TXT/JSON/HTML first,
PDFs never parsed) and capped — the registry stays JSON, not a blob store.
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import agent, judge  # noqa: E402
from src.evidence_fetch import EvidenceRecord, record_evidence  # noqa: E402

TEXT_CAP = 200_000


def _manifest_text(raw: Path) -> str:
    parts = []
    for path in judge._readable_files(raw):
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        parts.append(text)
        if sum(len(part) for part in parts) > TEXT_CAP:
            break
    return re.sub(r"\s+", " ", " ".join(parts)).strip()[:TEXT_CAP]


def backfill_drug(drug: str, dry_run: bool = False, with_text: bool = True) -> dict:
    """Fold every snapshot manifest for a drug into its pointer registry."""
    from src.agent import content_path, _slug

    root = content_path("sources", _slug(drug))
    stats = {"manifests": 0, "records": 0, "with_text": 0}
    if not root.exists():
        return stats
    for snapshot in sorted(root.iterdir()):
        if not snapshot.is_dir() or snapshot.name.startswith("."):
            continue
        if snapshot.name == "registry.json":
            continue
        for entry in sorted(snapshot.iterdir()):
            manifest_path = entry / "manifest.json"
            if not manifest_path.exists():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except ValueError:
                continue
            registry = manifest.get("registry", {})
            url = registry.get("url", "")
            source_id = manifest.get("source_id", entry.name)
            if not url and not source_id:
                continue
            stats["manifests"] += 1
            files = manifest.get("files", [])
            identifiers = registry.get("identifiers", {})
            coverage = manifest.get("coverage", {})
            text = _manifest_text(entry / "raw") if with_text else ""
            from src.evidence_fetch import version_pin
            record = EvidenceRecord(
                url=url,
                source_key=judge.source_key(url or source_id),
                source_id=source_id,
                title=registry.get("title", "") or entry.name,
                kind=registry.get("kind", ""),
                retrieved_at=manifest.get("fetched_at", ""),
                sha256=(hashlib.sha256("".join(
                    item.get("sha256", "") for item in files).encode()).hexdigest()
                    if files else ""),
                text=text,
                version_pin=version_pin(url, {**identifiers, **coverage}),
                access_level=manifest.get("access_level", ""),
                fetch_tier="snapshot",
                final_url=url,
                note="backfilled from snapshot manifest",
            )
            if text:
                stats["with_text"] += 1
            if not dry_run:
                agent.record_source_evidence(drug, record)
            stats["records"] += 1
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--drug", default="", help="Drug id (default: every drug with snapshots)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-text", action="store_true",
                        help="Pointer-only records; skip copying readable text")
    args = parser.parse_args()
    from src.agent import content_path
    sources = content_path("sources")
    drugs = [args.drug] if args.drug else sorted(
        path.name for path in sources.iterdir() if path.is_dir())
    total = {"manifests": 0, "records": 0, "with_text": 0}
    for drug in drugs:
        stats = backfill_drug(drug, dry_run=args.dry_run, with_text=not args.no_text)
        for key in total:
            total[key] += stats[key]
        print(f"{drug}: {stats['records']} records from {stats['manifests']} manifests "
              f"({stats['with_text']} with text)" + (" [dry run]" if args.dry_run else ""))
    print(f"total: {total['records']} records from {total['manifests']} manifests")


if __name__ == "__main__":
    main()
