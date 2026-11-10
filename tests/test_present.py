"""Text-to-PPTX builder: zip layout, XML validity, escaping."""

import io
import xml.etree.ElementTree as ET
import zipfile

import pytest

from src.present import build_narration, build_pdf, build_pptx, parse_sections


def test_parse_sections_splits_blocks_and_strips_markers():
    sections = parse_sections("Intro\n\nDosing\n- once daily\n* with food\n\nSafety\n1) rash\n2) nausea\n")
    assert [section["heading"] for section in sections] == ["Intro", "Dosing", "Safety"]
    assert sections[1]["bullets"] == ["once daily", "with food"]
    assert sections[2]["bullets"] == ["rash", "nausea"]


def test_build_pptx_has_title_slide_plus_sections():
    payload = build_pptx("Ibrance", [{"heading": "Dosing", "bullets": ["once daily"]}])
    assert payload[:2] == b"PK"
    package = zipfile.ZipFile(io.BytesIO(payload))
    names = set(package.namelist())
    assert "ppt/slides/slide1.xml" in names
    assert "ppt/slides/slide2.xml" in names
    assert "ppt/slides/slide3.xml" not in names


def test_build_pptx_every_part_parses_and_rels_resolve():
    payload = build_pptx("T & <C>", [{"heading": "A&B", "bullets": ["x < y", "say \"hi\""]}])
    package = zipfile.ZipFile(io.BytesIO(payload))
    for name in package.namelist():
        if name.endswith((".xml", ".rels")):
            ET.fromstring(package.read(name))  # must parse, escaping must hold
    # every relationship target must exist in the package
    for name in package.namelist():
        if name.endswith(".rels"):
            root = ET.fromstring(package.read(name))
            # .rels targets resolve against the part they describe: the parent
            # of the _rels directory, or the package root for _rels/.rels.
            base = name.split("/_rels/")[0] if "/_rels/" in name else ""
            for rel in root.iter():
                target = rel.attrib.get("Target", "")
                if target.startswith(("http", "/")) or not target:
                    continue
                resolved = "/".join(part for part in (base + "/" + target).split("/") if part not in ("", "."))
                stack = []
                for part in resolved.split("/"):
                    if part == "..":
                        stack.pop()
                    else:
                        stack.append(part)
                assert "/".join(stack) in package.namelist(), (name, target)
    body = package.read("ppt/slides/slide1.xml").decode("utf-8")
    assert "T &amp; &lt;C&gt;" in body


def test_presentations_endpoint_downloads_valid_pptx():
    from fastapi.testclient import TestClient

    from api.main import app

    client = TestClient(app)
    assert client.post("/api/presentations", json={"title": "", "text": "  \n "}).status_code == 400
    response = client.post("/api/presentations", json={"title": "Ibrance", "text": "Dosing\n- once daily\n\nSafety\n- rash"})
    assert response.status_code == 201
    assert "presentationml.presentation" in response.headers["content-type"]
    package = zipfile.ZipFile(io.BytesIO(response.content))
    assert "ppt/slides/slide3.xml" in package.namelist()


def test_build_pptx_caps_slide_and_bullet_counts():
    sections = [{"heading": f"H{i}", "bullets": [f"b{j}" for j in range(50)]} for i in range(60)]
    payload = build_pptx("Big", sections)
    package = zipfile.ZipFile(io.BytesIO(payload))
    slides = [name for name in package.namelist() if name.startswith("ppt/slides/slide")]
    assert len([name for name in slides if not name.endswith(".rels")]) == 31  # title + 30


def test_build_pdf_starts_with_header_and_holds_text():
    payload = build_pdf("Ibrance", [{"heading": "Dosing", "bullets": ["once daily"]}])
    assert payload[:5] == b"%PDF-"
    text = payload.decode("latin-1")
    assert "Ibrance" in text
    assert "Dosing" in text


def test_presentations_pdf_endpoint_downloads_valid_pdf():
    from fastapi.testclient import TestClient

    from api.main import app

    client = TestClient(app)
    assert client.post("/api/presentations/pdf", json={"title": "", "text": "  \n "}).status_code == 400
    response = client.post("/api/presentations/pdf", json={"title": "Ibrance", "text": "Dosing\n- once daily"})
    assert response.status_code == 201
    assert "application/pdf" in response.headers["content-type"]
    assert response.content[:5] == b"%PDF-"


def test_pptx_shapes_carry_alt_text_and_language():
    payload = build_pptx("T", [{"heading": "H", "bullets": ["b"]}], lang="es")
    package = zipfile.ZipFile(io.BytesIO(payload))
    body = package.read("ppt/slides/slide2.xml").decode("utf-8")
    assert 'descr="H"' in body
    assert 'lang="es"' in body


def test_pdf_carries_language_and_outline():
    payload = build_pdf("T", [{"heading": "H1", "bullets": ["b1"]}, {"heading": "H2", "bullets": ["b2"]}])
    assert b"/Lang (en-US)" in payload and b"/Outlines" in payload
    assert b"/Title" in payload


def test_build_narration_chunks_speakable_text_with_timing():
    sections = parse_sections("Dosing\n- once daily with food\n\nSafety\n- watch for neutropenia and dose reduce")
    narration = build_narration("Ibrance", sections)
    assert narration["chunks"]
    assert narration["total_seconds"] >= sum(chunk["seconds"] for chunk in narration["chunks"]) - 0.01
    assert all(chunk["words"] > 0 and chunk["seconds"] >= 1 for chunk in narration["chunks"])
    assert "once daily" in " ".join(chunk["text"] for chunk in narration["chunks"])


def test_narration_rate_and_clause_chunking():
    sections = parse_sections("Dosing\n- once daily with food, in the morning\n\nSafety\n- watch for neutropenia")
    slow = build_narration("Ibrance", sections, wpm=100)
    fast = build_narration("Ibrance", sections, wpm=200)
    assert slow["total_seconds"] > fast["total_seconds"]
    assert slow["chunks"] and all(chunk["words"] > 0 for chunk in slow["chunks"])
    with pytest.raises(ValueError, match="wpm"):
        build_narration("Ibrance", sections, wpm=500)


def test_narration_endpoint_returns_chunks_for_read_through():
    from fastapi.testclient import TestClient

    from api.main import app

    client = TestClient(app)
    assert client.post("/api/narration", json={"title": "", "text": "  \n "}).status_code == 400
    response = client.post("/api/narration", json={"title": "Ibrance", "text": "Dosing\n- once daily"})
    assert response.status_code == 201
    body = response.json()
    assert body["chunks"] and body["total_seconds"] > 0
