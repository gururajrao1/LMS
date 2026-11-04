"""Text-to-PPTX builder: zip layout, XML validity, escaping."""

import io
import xml.etree.ElementTree as ET
import zipfile

from src.present import build_pptx, parse_sections


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
