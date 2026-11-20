"""Fetch and store local evidence for the Patient Recruitment course.

The ClairLabs deck already cites recruitment literature, but those pages were
never held under `.pharmalearn/sources/`. This script:

  1. Discovers additional open literature via Europe PMC (seed queries)
  2. Fetches curated + discovered URLs through the same evidence chain the
     rest of the app uses (`fetch_evidence` / `record_evidence`)
  3. Writes a timestamped snapshot with readable HTML/text copies
  4. Extends the course `source_manifest.json` so Knowledge hub / checks /
     demos have local material without re-hitting the network

    uv run python scripts/fetch_patient_recruitment_sources.py
    uv run python scripts/fetch_patient_recruitment_sources.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.agent import _slug, content_path  # noqa: E402
from src.evidence_fetch import (  # noqa: E402
    _abstract_via_europepmc,
    _abstract_via_pubmed,
    _europepmc_search,
    fetch_evidence,
    record_evidence,
)

DRUG = "Patient Recruitment"
RUN_ID = "patient-recruitment-2026"

# Curated demo pack: open pages / PMC articles that back the ClairLabs deck.
CURATED = [
    {
        "id": "jmir-online-recruitment-meta",
        "title": "Online Patient Recruitment in Clinical Trials: Systematic Review and Meta-Analysis",
        # JMIR HTML returns HTTP 202 to bots; PMC OA mirror is the durable hold.
        "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC7673977/",
        "locator": "JMIR 2020;22(11):e22179 / PMC7673977",
        "why": "Online vs offline recruitment rate and cost-per-enrollee.",
    },
    {
        "id": "jmir-social-media-scoping",
        "title": "The Role of Social Media in Enhancing Clinical Trial Recruitment: Scoping Review",
        "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC7652693/",
        "locator": "JMIR 2020;22(10):e22810 / PMC7652693",
        "why": "Social media contribution to enrollment and cost range.",
    },
    {
        "id": "pmc-digital-tech-diversity",
        "title": "Digital technologies used in clinical trial recruitment and enrollment including application to trial diversity and inclusion",
        "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC10981266/",
        "locator": "PMC10981266",
        "why": "Digital recruitment tech landscape and diversity gaps.",
    },
    {
        "id": "pmc-digital-tools-map",
        "title": "Digital tools for the recruitment and retention of participants in randomised controlled trials: a systematic map",
        "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC7273688/",
        "locator": "PMC7273688",
        "why": "Map of digital recruitment/retention tools over a decade.",
    },
    {
        "id": "pmc-minority-accrual",
        "title": "Interventions to increase racial and ethnic minority accrual into cancer clinical trials",
        "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC10456972/",
        "locator": "PMC10456972",
        "why": "What actually moves minority accrual (navigation, education).",
    },
    {
        "id": "pmc-video-diversity",
        "title": "Use of Video Education Interventions to Increase Racial and Ethnic Diversity in Cancer Clinical Trials",
        "url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8483572/",
        "locator": "PMC8483572",
        "why": "Video education as a recruitment diversity lever.",
    },
    {
        "id": "pmc-digital-dei",
        "title": "Leveraging digital tools to enhance diversity and inclusion in clinical trial recruitment",
        "url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11550947/",
        "locator": "PMC11550947",
        "why": "Practical digital DEI recruitment tactics and barriers.",
    },
    {
        "id": "trialnotice-enrollment-stats",
        "title": "Clinical trial enrollment statistics and site performance benchmarks",
        "url": "https://www.trialnotice.com/blog/clinical-trial-enrollment-statistics/",
        "locator": "TrialNotice / Tufts CSDD benchmarks",
        "why": "Zero-enroll / under-enroll / screen-failure / dropout benchmarks.",
    },
    {
        "id": "springer-advocacy-recruitment",
        "title": "Patient advocacy and community engagement in clinical trial recruitment",
        "url": "https://link.springer.com/article/10.1186/s12913-024-11376-3",
        "locator": "BMC Health Serv Res 2024",
        "why": "Advocacy/PAG partnerships and recruitment timelines.",
    },
]

DISCOVER_QUERIES = [
    'TITLE:"clinical trial recruitment" AND TITLE:"social media"',
    'TITLE:"patient recruitment" AND TITLE:"digital" AND (REVIEW)',
    'TITLE:"clinical trial" AND TITLE:"enrollment" AND TITLE:"digital tools"',
]


def _discover(limit: int = 6) -> list[dict]:
    """Europe PMC hits that are not already in the curated list."""
    seen = {item["url"].rstrip("/") for item in CURATED}
    # Also skip PMC mirrors of curated JMIR papers.
    seen.update({
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC7673977",
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC7652693",
    })
    found: list[dict] = []
    for query in DISCOVER_QUERIES:
        for hit in _europepmc_search(query)[:8]:
            pmcid = (hit.get("pmcid") or "").upper()
            pmid = hit.get("pmid") or ""
            title = (hit.get("title") or "").strip()
            if not title:
                continue
            if pmcid:
                url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/"
            elif pmid:
                url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            else:
                continue
            key = url.rstrip("/")
            if key in seen:
                continue
            seen.add(key)
            found.append({
                "id": f"epmc-{(pmcid or pmid).lower()}",
                "title": title[:180],
                "url": url,
                "locator": pmcid or f"PMID {pmid}",
                "pmid": pmid,
                "why": f"Europe PMC discovery: {query[:60]}",
            })
            if len(found) >= limit:
                return found
    return found


def _fetch_with_fallback(source: dict):
    """Direct fetch first; fall back to PubMed/Europe PMC abstract if thin."""
    record = fetch_evidence(source["url"], brand=DRUG, title=source["title"])
    if record.text and len(record.text) > 500 and record.access_level != "unavailable":
        return record
    pmid = source.get("pmid") or ""
    if not pmid:
        # Pull PMID from a PMC / PubMed URL when present.
        match = re.search(r"(?:pubmed\.ncbi\.nlm\.nih\.gov|PMID[:\s])[/:]?(\d{5,})", source["url"], re.I)
        if match:
            pmid = match.group(1)
    if not pmid:
        return record
    for attempt in (_abstract_via_pubmed, _abstract_via_europepmc):
        try:
            alt = attempt(pmid)
        except Exception:
            alt = None
        if alt and alt.text and len(alt.text) > 200:
            alt.url = source["url"]
            return alt
    return record


def _excerpt(text: str, limit: int = 600) -> str:
    clean = re.sub(r"\s+", " ", (text or "").strip())
    return clean if len(clean) <= limit else clean[: limit - 1].rstrip() + "…"


def _write_snapshot(source: dict, record, snapshot: Path) -> dict:
    folder = snapshot / source["id"]
    raw = folder / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    text = record.text or ""
    if text:
        (raw / "document.txt").write_text(text, encoding="utf-8")
    manifest = {
        "source_id": source["id"],
        "title": source["title"],
        "url": source["url"],
        "locator": source["locator"],
        "why": source["why"],
        "fetched_at": record.retrieved_at,
        "access_level": record.access_level,
        "fetch_tier": record.fetch_tier,
        "sha256": record.sha256,
        "characters": len(text),
        "note": record.note,
        "final_url": record.final_url or source["url"],
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _update_course_manifest(entries: list[dict]) -> None:
    path = content_path("content", RUN_ID, "source_manifest.json")
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
        "accessed_at": "", "scope": "", "sources": [],
    }
    by_url = {
        (item.get("url") or item.get("title") or "").rstrip("/"): item
        for item in existing.get("sources", [])
    }
    for entry in entries:
        key = (entry.get("url") or entry.get("title") or "").rstrip("/")
        by_url[key] = {
            "title": entry["title"],
            "url": entry.get("url", ""),
            "locator": entry.get("locator", ""),
            "supporting_text": entry.get("supporting_text", ""),
            "held_locally": True,
            "access_level": entry.get("access_level", ""),
            "retrieved_at": entry.get("retrieved_at", ""),
        }
    existing["sources"] = list(by_url.values())
    existing["accessed_at"] = datetime.now(UTC).isoformat()
    existing["scope"] = (
        "Course deck plus locally fetched recruitment literature "
        "(JMIR / PMC / benchmarks) for offline demo use"
    )
    path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")

    # Keep the journey build step honest about how much evidence we hold.
    manifest_path = content_path("content", RUN_ID, "manifest.json")
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["citation_count"] = max(
            int(manifest.get("citation_count") or 0),
            len(existing["sources"]),
        )
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--discover", type=int, default=6,
                        help="Extra Europe PMC discoveries to attempt (default 6)")
    args = parser.parse_args()

    pack = list(CURATED) + _discover(limit=args.discover)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    snapshot = content_path("sources", _slug(DRUG), stamp)
    print(f"drug={DRUG} slug={_slug(DRUG)} sources={len(pack)} dry_run={args.dry_run}")
    if not args.dry_run:
        snapshot.mkdir(parents=True, exist_ok=True)

    held: list[dict] = []
    for source in pack:
        print(f"FETCH  {source['id']}", flush=True)
        record = _fetch_with_fallback(source)
        usable = bool(record.text) and len(record.text) > 100 and record.access_level != "unavailable"
        status = "HIT" if usable else "MISS"
        print(
            f"{status:4}  {record.fetch_tier}/{record.access_level} "
            f"chars={len(record.text or '')} {record.note[:80]}",
            flush=True,
        )
        if args.dry_run:
            continue
        if usable:
            record_evidence(DRUG, record)
            _write_snapshot(source, record, snapshot)
            held.append({
                "title": source["title"],
                "url": source["url"],
                "locator": source["locator"],
                "supporting_text": _excerpt(record.text) or source["why"],
                "access_level": record.access_level,
                "retrieved_at": record.retrieved_at,
            })
        else:
            # Still note the pointer so the demo can show what was attempted.
            held.append({
                "title": source["title"],
                "url": source["url"],
                "locator": source["locator"],
                "supporting_text": source["why"] + (
                    f" (fetch: {record.note or record.access_level})" if record.note or record.access_level else ""
                ),
                "access_level": record.access_level or "unavailable",
                "retrieved_at": record.retrieved_at,
            })

    if not args.dry_run:
        (snapshot / "snapshot.json").write_text(
            json.dumps({
                "drug": DRUG,
                "run_id": RUN_ID,
                "fetched_at": datetime.now(UTC).isoformat(),
                "source_count": len(pack),
                "held_with_text": sum(1 for item in held if item.get("access_level") not in {"", "unavailable"}),
            }, indent=2) + "\n",
            encoding="utf-8",
        )
        _update_course_manifest(held)
        print(f"snapshot {snapshot}")
        print(f"registry {content_path('sources', _slug(DRUG), 'registry.json')}")
        print(f"course   {content_path('content', RUN_ID, 'source_manifest.json')}")
    print(f"done: attempted={len(pack)} held_entries={len(held)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
