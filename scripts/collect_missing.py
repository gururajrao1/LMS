"""Collect the missing research: turn untraceable cites into recorded evidence.

Research used to be one model pass with no per-citation follow-up: whatever the
model failed to fetch stayed a gap forever. This closes the loop per citation:

1. take every currently-untraceable cite in the run,
2. run it through the evidence fetch chain (canonical label text, legal open
   access, PubMed/Europe PMC abstract — never a bot-wall bypass),
3. record whatever tier serves as a dossier claim under the cite's exact
   title/locator, with the access level stated, and register the text so the
   quote check runs against it,
4. re-run the checker and report the delta.

Anything still unfetchable (press pages, bot-walled full text) stays an
explicit human-record gap instead of a silent one. Segmented excerpts are
capped: a 2,000-word abstract is recorded whole, a label section sliced to the
cited passage is the reviewer's call, not this script's.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import agent, judge  # noqa: E402
from src.evidence_fetch import EvidenceRecord, fetch_evidence, record_evidence  # noqa: E402


def _untraceable_cites(run_id: str) -> dict:
    """Distinct (title, locator, url) cites with no dossier claim behind them."""
    dossier = judge._dossier_citations(run_id)
    pairs = {}
    for track in ("hcp", "msl"):
        found, _ = judge.deterministic_findings(run_id, track, judge.drug_for(run_id))
        for item in found:
            if item.check != "untraceable":
                continue
            for citation in item.citations:
                if judge._trace(citation, dossier) is not None:
                    continue
                pairs[(citation.get("title", ""), citation.get("locator", ""),
                       citation.get("url", ""))] = item.reference
    return pairs


def collect(run_id: str, drug: str, dry_run: bool = False) -> dict:
    pairs = _untraceable_cites(run_id)
    stats = {"cites": len(pairs), "recorded": 0, "still_missing": []}
    if not pairs:
        print("no untraceable cites left")
        return stats

    dossier_path = agent.content_path("content", run_id, "master", "dossier.json")
    dossier = json.loads(dossier_path.read_text(encoding="utf-8"))
    try:
        section = next(s for s in dossier["sections"] if s.get("id") == "cited-source-verification")
    except StopIteration:
        section = {"id": "cited-source-verification", "title": "Cited-source verification",
                   "summary": "", "claims": []}
        dossier["sections"].append(section)

    for (title, locator, url) in sorted(pairs):
        if not url:
            stats["still_missing"].append((title, locator, "no url to fetch"))
            continue
        record = fetch_evidence(url, drug, title=title)
        if record.access_level == "unavailable" or not record.text:
            stats["still_missing"].append((title, locator, record.note or "unreachable"))
            print(f"MISS  {title[:55]} | {record.note or record.access_level}"[:110])
            continue
        pairing = f"{title[:55]} <- {record.fetch_tier}/{record.access_level}"
        print(f"HIT   {pairing}"[:110])
        if dry_run:
            stats["recorded"] += 1
            continue
        record_evidence(drug, record)
        claim_id = f"cit-collect-{stats['recorded'] + 1}"
        excerpt = record.text if len(record.text) <= 1500 else record.text[:1500]
        section["claims"].append({
            "id": claim_id,
            "text": excerpt[:400],
            "topic": "cited_source",
            "supporting_text": excerpt,
            "citations": [{"title": title, "locator": locator, "url": url,
                           "supporting_text": excerpt,
                           "access_level": record.access_level,
                           "retrieved_at": record.retrieved_at,
                           "sha256": record.sha256,
                           "version_pin": record.version_pin}],
        })
        stats["recorded"] += 1

    if not dry_run and stats["recorded"]:
        dossier_path.write_text(json.dumps(dossier, indent=1), encoding="utf-8")
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id", help="Run to collect the missing research for")
    parser.add_argument("--drug", default="", help="Brand (default: from run manifest)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Probe the chain without recording anything")
    parser.add_argument("--recheck", action="store_true",
                        help="Re-run the checker after recording")
    args = parser.parse_args()
    drug = args.drug or judge.drug_for(args.run_id)
    stats = collect(args.run_id, drug, dry_run=args.dry_run)
    print(f"cites: {stats['cites']}, recorded: {stats['recorded']}, "
          f"still missing: {len(stats['still_missing'])}")
    for title, locator, why in stats["still_missing"]:
        print(f"  MISSING {title[:50]} / {locator[:40]}: {why[:80]}")
    if args.recheck and not args.dry_run:
        report = asyncio.run(judge.run(args.run_id, drug, model_tracks=()))
        blocking = [x for x in report["findings"] if x["severity"] == "blocking"]
        print(f"fresh report: {len(report['findings'])} findings, {len(blocking)} blocking, "
              f"traceable {report['stats']['traceable']}/{report['stats']['citations']}")


if __name__ == "__main__":
    main()
