"""Focused tests for the remote-first evidence layer (src/evidence_fetch.py).

All network is faked: every test injects a handler, so the suite never leaves
the machine. Live endpoint shapes are probed separately, not here.
"""

import json

import httpx
import pytest

from src import evidence_fetch
from src.evidence_fetch import (
    EvidenceRecord,
    content_sha256,
    fetch_evidence,
    fetch_url,
    read_registry,
    record_evidence,
    version_pin,
)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(evidence_fetch, "_sleep", lambda seconds: None)
    monkeypatch.setattr(evidence_fetch, "_last_hit", {})


def make_response(url, status=200, content=b"", ctype="text/html"):
    request = httpx.Request("GET", url)
    return httpx.Response(status, headers={"content-type": ctype},
                          content=content, request=request)


def handler_for(mapping):
    def handle(url, headers, timeout):
        assert "PharmaLearn" in headers.get("User-Agent", ""), "honest UA required"
        assert "contact" in headers.get("User-Agent", ""), "contact in UA required"
        key = next((prefix for prefix in mapping if url.startswith(prefix)), None)
        assert key is not None, f"unexpected fetch of {url}"
        return mapping[key]
    return handle


def test_version_pin_reads_url_and_metadata():
    assert version_pin("https://x/y?setid=abc&version=10") == "version:10"
    assert version_pin("https://x/y", {"published_date": "2024-01-01"}) == (
        "published_date:2024-01-01")
    assert version_pin("https://x/y") == ""


def test_content_sha256_stable():
    assert content_sha256(b"abc") == content_sha256(b"abc")
    assert content_sha256(b"abc") != content_sha256(b"abd")


def test_direct_html_fetch_records_text():
    handler = handler_for({
        "https://example.com/page": make_response(
            "https://example.com/page",
            content=b"<h1>Hello</h1><p>" + b"world and more evidence text here. " * 6 + b"</p>")})
    record = fetch_evidence("https://example.com/page", handler=handler)
    assert record.access_level == "fetched_live"
    assert record.fetch_tier == "direct"
    assert "Hello world" in record.text
    assert len(record.sha256) == 64


def test_http_error_becomes_unavailable_not_exception():
    handler = handler_for({
        "https://example.com/gone": make_response(
            "https://example.com/gone", status=404, content=b"nope")})
    record = fetch_evidence("https://example.com/gone", handler=handler)
    assert record.access_level == "unavailable"
    assert "404" in record.note


def test_pdf_bytes_are_not_parsed_as_text():
    handler = handler_for({
        "https://example.com/label.pdf": make_response(
            "https://example.com/label.pdf", content=b"%PDF-1.4 fake",
            ctype="application/pdf")})
    record = fetch_evidence("https://example.com/label.pdf", handler=handler)
    assert record.access_level == "unavailable"
    assert "PDF" in record.note


def test_robots_disallow_is_respected():
    def deny(url, headers, timeout):
        raise AssertionError("must not fetch when disallowed")
    deny.robots = False
    record = fetch_evidence("https://example.com/page", handler=deny)
    assert record.access_level == "unavailable"
    assert "robots" in record.note


def test_label_cite_prefers_openfda_text():
    label_json = (b'{"results": [{"openfda": {"spl_version_date": "2025-04-01"}, '
                  b'"warnings": ["Interrupt IBRANCE immediately in suspected ILD. '
                  + b"x" * 600 + b'"]}]}')
    handler = handler_for({
        "https://api.fda.gov/drug/label.json": make_response(
            "https://api.fda.gov/drug/label.json", content=label_json,
            ctype="application/json")})
    record = fetch_evidence(
        "https://www.accessdata.fda.gov/drugsatfda_docs/label/2025/x.pdf",
        brand="Ibrance", handler=handler)
    assert record.fetch_tier == "canonical_label"
    assert record.access_level == "fetched_live"
    assert "Interrupt IBRANCE immediately" in record.text
    assert record.version_pin == "revision_date:2025-04-01"


def test_label_cite_falls_back_to_dailymed_xml():
    spls = (b'{"data": {"spls": [{"setid": "e0e6412f-50b4-4fd4-9364-62818d121a07", '
            b'"title": "IBRANCE capsules", "published_date": "2025-01-01"}]}}')
    xml = b"<document><text>Grade 3 neutropenia: withhold. " + b"y" * 600 + b"</text></document>"
    handler = handler_for({
        "https://api.fda.gov/drug/label.json": make_response(
            "https://api.fda.gov/drug/label.json", status=500, content=b"err"),
        "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json": make_response(
            "https://dailymed.nlm.nih.gov/x", content=spls, ctype="application/json"),
        "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/e0e6412f": make_response(
            "https://dailymed.nlm.nih.gov/x", content=xml, ctype="application/xml")})
    record = fetch_evidence("https://labeling.pfizer.com/showlabeling.aspx?id=2191",
                            brand="Ibrance", handler=handler)
    assert record.fetch_tier == "canonical_label"
    assert "Grade 3 neutropenia" in record.text


def test_publisher_doi_uses_oa_when_allowed():
    unpay = (b'{"is_oa": true, "best_oa_location": '
             b'{"url_for_pdf": "", "url": "https://oa.example.com/paper", '
             b'"title": "Palbociclib study"}}')
    article = b"<html><body>Median PFS was 24.8 months. " + b"z" * 600 + b"</body></html>"
    handler = handler_for({
        "https://api.unpaywall.org/v2/10.1056": make_response(
            "https://api.unpaywall.org/v2/x", content=unpay, ctype="application/json"),
        "https://oa.example.com/paper": make_response(
            "https://oa.example.com/paper", content=article)})
    record = fetch_evidence("https://www.nejm.org/doi/full/10.1056/NEJMoa1607303",
                            handler=handler)
    assert record.fetch_tier == "open_access"
    assert record.access_level == "fetched_live"
    assert "24.8 months" in record.text


def test_publisher_doi_falls_back_to_pubmed_abstract():
    unpay = b'{"is_oa": false}'
    esearch = b'{"esearchresult": {"idlist": ["27406346"]}}'
    efetch = (b"<PubmedArticle><ArticleTitle>Palbociclib study</ArticleTitle>"
              b"<Abstract><AbstractText>Median PFS was 24.8 versus 14.5 months "
              b"in the trial population studied here.</AbstractText></Abstract>"
              b"</PubmedArticle>")
    handler = handler_for({
        "https://api.unpaywall.org/v2/10.1056": make_response(
            "https://api.unpaywall.org/v2/x", content=unpay, ctype="application/json"),
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi": make_response(
            "https://eutils.ncbi.nlm.nih.gov/x",
            content=esearch, ctype="application/json"),
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi": make_response(
            "https://eutils.ncbi.nlm.nih.gov/x",
            content=efetch, ctype="application/xml")})
    record = fetch_evidence("https://www.nejm.org/doi/full/10.1056/NEJMoa1607303",
                            handler=handler)
    assert record.fetch_tier == "abstract_only"
    assert record.access_level == "abstract_only"
    assert "24.8 versus 14.5" in record.text


def test_registry_round_trip_latest_wins(monkeypatch, tmp_path):
    monkeypatch.setattr("src.agent.DATA", tmp_path)
    first = EvidenceRecord(url="https://example.com/a", source_key="example:a",
                           retrieved_at="2025-01-01T00:00:00+00:00",
                           text="old text", sha256="0" * 64,
                           access_level="fetched_live")
    record_evidence("Ibrance", first)
    second = EvidenceRecord(url="https://example.com/a", source_key="example:a",
                            retrieved_at="2026-01-01T00:00:00+00:00",
                            text="new text", sha256="1" * 64,
                            access_level="fetched_live")
    path = record_evidence("Ibrance", second)
    assert path.exists()
    registry = read_registry("Ibrance")
    assert registry["example:a"]["text"] == "new text"
    assert registry["example:a"]["registry_version"] == "1"


def test_backfill_folds_manifests_into_the_registry(monkeypatch, tmp_path):
    from scripts.backfill_registry import backfill_drug
    monkeypatch.setattr("src.agent.DATA", tmp_path)
    snap = tmp_path / "sources" / "ibrance" / "20260101T000000Z" / "label"
    (snap / "raw").mkdir(parents=True)
    (snap / "manifest.json").write_text(json.dumps({
        "source_id": "ibrance-label-capsule",
        "fetched_at": "2026-01-01T00:00:00+00:00",
        "access_level": "full_text",
        "coverage": {},
        "registry": {
            "title": "IBRANCE capsule",
            "url": "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=e0e6412f-50b4-4fd4-9364-62818d121a07",
            "identifiers": {"set_id": "e0e6412f-50b4-4fd4-9364-62818d121a07",
                            "spl_version": "24"},
        },
        "files": [{"path": "raw/spl.xml", "sha256": "ab" * 32}],
    }))
    (snap / "raw" / "spl.xml").write_text("<doc><p>Monitor counts each cycle.</p></doc>")

    stats = backfill_drug("Ibrance", dry_run=False)
    assert stats == {"manifests": 1, "records": 1, "with_text": 1}
    registry = read_registry("Ibrance")
    key = "dailymed:e0e6412f-50b4-4fd4-9364-62818d121a07"
    assert key in registry
    assert registry[key]["version_pin"] == "set_id:e0e6412f-50b4-4fd4-9364-62818d121a07"
    assert "Monitor counts each cycle." in registry[key]["text"]
    assert registry[key]["source_id"] == "ibrance-label-capsule"

    # Idempotent: a second run changes nothing.
    again = backfill_drug("Ibrance", dry_run=False)
    assert again == stats
    assert len(read_registry("Ibrance")) == 1


def test_backfill_dry_run_writes_nothing(monkeypatch, tmp_path):
    from scripts.backfill_registry import backfill_drug
    monkeypatch.setattr("src.agent.DATA", tmp_path)
    snap = tmp_path / "sources" / "ibrance" / "20260101T000000Z" / "label"
    (snap / "raw").mkdir(parents=True)
    (snap / "manifest.json").write_text(json.dumps({
        "source_id": "x", "fetched_at": "2026-01-01T00:00:00+00:00",
        "registry": {"url": "https://example.com/x", "title": "X"},
        "files": [],
    }))
    stats = backfill_drug("Ibrance", dry_run=True)
    assert stats["records"] == 1
    assert read_registry("Ibrance") == {}
