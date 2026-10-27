"""The reference library: what we hold, and how it reads.

"Source" on a course means a link someone recorded. "Held" is the stronger claim
this feature rests on — the file is on disk, it is what the checker matched
quotes against, and it can be read without trusting the publisher still serves
that URL. These tests protect the difference between the two, and the ordering
that decides what a reader sees first.
"""

import json

import pytest

from api.main import library, library_document
from fastapi import HTTPException
from src import agent, judge

LABEL_XML = """<document><title>IBRANCE (palbociclib) capsules</title>
<section>Withhold IBRANCE until recovery to Grade 2 or lower.</section></document>"""
HISTORY_JSON = '{"spl_version": 24, "published_date": "2026-01-01"}'


@pytest.fixture
def stored(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "DATA", tmp_path)
    run = tmp_path / "content" / "run"
    run.mkdir(parents=True)
    (run / "manifest.json").write_text(json.dumps({
        "drug": {"brand": "Ibrance", "generic": "Palbociclib", "area": "Oncology"}}))
    (run / "source_manifest.json").write_text(json.dumps({"sources": [
        # The same SPL under two spellings — exactly what `source_key` collapses.
        {"title": "Label (drugInfo)", "publisher": "DailyMed",
         "url": "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=" + "a" * 8 + "-1111-2222-3333-" + "b" * 12},
        {"title": "Label (lookup)", "publisher": "DailyMed",
         "url": "https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid=" + "a" * 8 + "-1111-2222-3333-" + "b" * 12},
        {"title": "A page we only linked to", "publisher": "Pfizer",
         "url": "https://www.pfizer.com/news/press-release/whatever"},
    ]}))

    source = tmp_path / "sources" / "ibrance" / "20260101T000000Z" / "label"
    (source / "raw").mkdir(parents=True)
    (source / "raw" / "spl.xml").write_text(LABEL_XML)
    (source / "raw" / "history.json").write_text(HISTORY_JSON)
    (source / "manifest.json").write_text(json.dumps({
        "source_id": "label", "fetched_at": "2026-01-01T00:00:00+00:00", "access_level": "full_text",
        "registry": {"kind": "current_fda_label", "title": "IBRANCE label",
                     "url": "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid="
                            + "a" * 8 + "-1111-2222-3333-" + "b" * 12},
    }))
    return "run"


def test_the_document_reads_as_the_label_not_as_its_metadata(stored):
    """`history.json` sorts before `spl.xml`, so alphabetical order opened the US
    label on an API envelope. The document leads; its metadata follows."""
    text = judge.readable_source("Ibrance", "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid="
                                 + "a" * 8 + "-1111-2222-3333-" + "b" * 12)

    assert text.startswith("IBRANCE (palbociclib) capsules")
    # Nothing is dropped, only reordered — a quote can legitimately sit in either.
    assert "spl_version" in text


def test_held_is_a_narrower_claim_than_cited(stored):
    result = library(stored)

    held = [entry for entry in result["documents"] if entry["held"]]
    linked = [entry for entry in result["documents"] if not entry["held"]]
    assert [entry["title"] for entry in linked] == ["A page we only linked to"]
    assert len(held) == 1
    assert result["held"] == 1


def test_one_document_cited_under_two_urls_is_listed_once(stored):
    """Counting URL spellings would overstate how much of the evidence we hold."""
    result = library(stored)

    assert result["total"] == 2
    label = next(entry for entry in result["documents"] if entry["held"])
    assert label["listed_as"] == 2


def test_a_document_fetched_later_is_shown_even_though_it_was_never_listed(stored, tmp_path):
    """Citations resolved after the fact are held too; hiding them understates it."""
    extra = tmp_path / "sources" / "ibrance" / "20260202T000000Z" / "pmc"
    (extra / "raw").mkdir(parents=True)
    (extra / "raw" / "fulltext.xml").write_text("<article>Later fetch.</article>")
    (extra / "manifest.json").write_text(json.dumps({
        "source_id": "pmc", "fetched_at": "2026-02-02T00:00:00+00:00",
        "registry": {"kind": "pmc_article", "title": "A resolved citation",
                     "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC999/"},
    }))

    result = library(stored)
    resolved = next(entry for entry in result["documents"] if entry["title"] == "A resolved citation")

    assert resolved["held"] is True
    assert resolved["cited"] is False


def test_held_documents_are_listed_before_the_ones_we_only_link_to(stored):
    result = library(stored)
    assert [entry["held"] for entry in result["documents"]] == sorted(
        [entry["held"] for entry in result["documents"]], reverse=True)


def test_reading_a_document_we_do_not_hold_is_refused(stored):
    with pytest.raises(HTTPException) as raised:
        library_document(stored, url="https://www.pfizer.com/news/press-release/whatever")
    assert raised.value.status_code == 404


def test_a_held_document_is_served_whole_with_its_provenance(stored):
    served = library_document(stored, url="https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid="
                              + "a" * 8 + "-1111-2222-3333-" + "b" * 12)

    assert "Withhold IBRANCE until recovery" in served["text"]
    assert served["characters"] == len(served["text"])
    # Provenance travels with the text: a document with no date is just a file.
    assert served["fetched_at"].startswith("2026-01-01")
    assert served["kind"] == "current_fda_label"
