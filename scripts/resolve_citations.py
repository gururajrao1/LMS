"""Fetch the documents a course actually cites, so more of it can be checked.

`fetch_pfizer.py` fetches a hand-curated registry: the label, the pivotal trials,
a handful of papers. The generated course then cites far more than that, and every
citation whose document we do not hold is reported as *unverifiable* — honest, but
it is why coverage sits at a quarter of the citations rather than most of them.

This closes the gap from the other end. It reads the citations the course made,
keeps the ones that name a document on an open registry by a resolvable identifier,
and fetches those through the same handlers `fetch_pfizer.py` uses. The result is a
supplementary snapshot: nothing already stored is touched, and `judge.source_corpus`
reads every snapshot, so the new documents simply become checkable.

Only registries where the identifier names the document itself are followed:

  * DailyMed        setid      the SPL
  * PubMed          pmid       the record, and PMC full text when it links one
  * PMC             PMCxxxxx   the open-access article
  * ClinicalTrials  NCTxxxxx   the study record

Deliberately not followed: protocol PDFs on cdn.clinicaltrials.gov and historical
label PDFs on accessdata.fda.gov. We cannot read PDF text, and registering the
study record under a protocol's URL would check a quote against a document it was
never drawn from — a false answer, which is worse than an honest gap.

    uv run python scripts/resolve_citations.py --run <run-id> --dry-run
    uv run python scripts/resolve_citations.py --run <run-id>
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.fetch_pfizer import fetch_source  # noqa: E402
from src import judge  # noqa: E402
from src.agent import content_path  # noqa: E402

# Each rule turns a cited URL into the source entry a handler already understands.
RESOLVERS = (
    ("current_fda_label", "set_id",
     re.compile(r"dailymed\.nlm\.nih\.gov/.*?setid=([0-9a-f-]{36})", re.I),
     lambda value: value.lower()),
    ("peer_reviewed_publication", "pmid",
     re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)"), str),
    ("pmc_article", "pmcid",
     re.compile(r"(?:pmc\.ncbi\.nlm\.nih\.gov|ncbi\.nlm\.nih\.gov/pmc)/articles/(PMC\d+)", re.I),
     lambda value: value.upper()),
    ("trial_registry", "nct",
     re.compile(r"^https?://(?:www\.)?clinicaltrials\.gov/study/(NCT\d+)", re.I),
     lambda value: value.upper()),
)


def resolve(citation: dict) -> dict | None:
    """The source entry this citation names, or None if nothing resolvable."""
    url = citation.get("url", "")
    for kind, field, pattern, clean in RESOLVERS:
        found = pattern.search(url or "")
        if not found:
            continue
        identifier = clean(found.group(1))
        return {
            "id": f"{kind[:4]}-{re.sub(r'[^a-zA-Z0-9]+', '', identifier)[:28].lower()}",
            "kind": kind,
            "url": url,
            "title": citation.get("title", "") or identifier,
            "identifiers": {field: identifier},
        }
    return None


def wanted(run_id: str, drug: str) -> list[dict]:
    """Resolvable citations whose document we do not already hold, deduplicated."""
    held = judge.source_corpus(drug)
    found: dict[str, dict] = {}
    for claim in judge._dossier_citations(run_id).values():
        # No recorded quote means nothing to check the document against, so
        # fetching it would add weight without adding verification.
        if not claim.get("supporting_text"):
            continue
        source = resolve(claim)
        if not source or judge.source_key(source["url"]) in held:
            continue
        found.setdefault(judge.source_key(source["url"]), source)
    return list(found.values())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, help="run id whose citations to resolve")
    parser.add_argument("--drug", default="", help="registry drug folder (default: from the manifest)")
    parser.add_argument("--dry-run", action="store_true", help="list what would be fetched and stop")
    parser.add_argument("--limit", type=int, default=0, help="fetch at most this many (0 = all)")
    args = parser.parse_args()

    drug = args.drug or judge.drug_for(args.run)
    if not drug:
        parser.error("could not read the drug from the manifest; pass --drug")

    sources = wanted(args.run, drug)
    if args.limit:
        sources = sources[:args.limit]
    if not sources:
        print("Nothing to fetch: every resolvable citation is already held.")
        return 0

    print(f"{len(sources)} document(s) to fetch for {drug}:")
    for source in sources:
        print(f"    {source['kind']:<28} {list(source['identifiers'].values())[0]}")
    if args.dry_run:
        return 0

    snapshot_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    root = content_path("sources", judge._slug(drug))
    staging = root / f".{snapshot_id}.partial"
    staging.mkdir(parents=True)

    results = []
    headers = {"User-Agent": "PharmaLearn/0.2 source-audit (local development)"}
    with httpx.Client(headers=headers, follow_redirects=True, timeout=120) as client:
        for source in sources:
            print(f"FETCH   {source['id']}", flush=True)
            manifest = fetch_source(client, staging / source["id"], {"id": judge._slug(drug)}, source)
            results.append({key: manifest[key] for key in
                            ["source_id", "status", "access_level", "warnings", "error"]})
            print(f"{manifest['status'].upper():7} {source['id']} ({manifest['access_level']})", flush=True)

    failures = [item for item in results if item["status"] == "failed"]
    (staging / "snapshot.json").write_text(json.dumps({
        "schema_version": 2,
        "snapshot_id": snapshot_id,
        "drug_id": judge._slug(drug),
        "created_at": datetime.now(UTC).isoformat(),
        "status": "incomplete" if failures else "complete",
        "origin": "resolved_from_citations",
        "run_id": args.run,
        "sources": results,
    }, indent=2) + "\n")
    staging.replace(root / snapshot_id)

    usable = [item for item in results if item["access_level"] == "full_text"]
    print(f"\n{len(results) - len(failures)} fetched, {len(failures)} failed, "
          f"{len(usable)} with full text")
    print(root / snapshot_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
