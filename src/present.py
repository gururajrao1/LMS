"""Minimal PowerPoint builder with no third-party dependency.

Produces a real .pptx (Open Packaging Conventions zip) from a title plus
heading/bullet slides: one title slide and one content slide per section.
Every part needed by the format â€” content types, relationships, master,
layout, theme and one slide part per slide â€” is emitted, so PowerPoint,
Keynote and LibreOffice open the file without repair.
"""

import io
import re
import zipfile
from xml.sax.saxutils import escape

PDF_PAGE_WIDTH = 595
PDF_PAGE_HEIGHT = 842
PDF_MARGIN = 56
PDF_TOP = 786

MAX_SLIDES = 30
MAX_BULLETS = 8
MAX_TEXT = 500

APP_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><TotalTime>0</TotalTime><Words>0</Words><PresentationFormat>On-screen Show (16:9)</PresentationFormat><Paragraphs>0</Paragraphs><Slides>{slides}</Slides><Notes>0</Notes><HiddenSlides>0</HiddenSlides><MMClips>0</MMClips></Properties>"""

CORE_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>{title}</dc:title><dc:creator>PharmaLearn</dc:creator></cp:coreProperties>"""

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>{overrides}</Types>"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>"""

PRESENTATION = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst><p:sldIdLst>{slides}</p:sldIdLst><p:sldSz cx="12192000" cy="6858000" type="wide"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>"""

PRESENTATION_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>{slides}</Relationships>"""

MASTER = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld><p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/><p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst><p:txStyles><p:titleStyle><a:lvl1pPr><a:defRPr sz="4400" b="1"><a:solidFill><a:srgbClr val="1F2937"/></a:solidFill></a:defRPr></a:lvl1pPr></p:titleStyle><p:bodyStyle><a:lvl1pPr><a:defRPr sz="2000"><a:solidFill><a:srgbClr val="374151"/></a:solidFill></a:defRPr></a:lvl1pPr></p:bodyStyle><p:otherStyle><a:lvl1pPr><a:defRPr sz="1800"/></a:lvl1pPr></p:otherStyle></p:txStyles></p:sldMaster>"""

MASTER_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/></Relationships>"""

LAYOUT = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" type="titleBody" preserve="1"><p:cSld name="Title and Content"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr><p:sp><p:nvSpPr><p:cNvPr id="2" name="Title"/><p:cNvSpPr/><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr><p:spPr/></p:sp><p:sp><p:nvSpPr><p:cNvPr id="3" name="Content"/><p:cNvSpPr/><p:nvPr><p:ph type="body" idx="1"/></p:nvPr></p:nvSpPr><p:spPr/></p:sp></p:spTree></p:cSld><p:clrMapOvr><a:overrideClrMapping bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/></p:clrMapOvr></p:sldLayout>"""

LAYOUT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/></Relationships>"""

THEME = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="PharmaLearn"><a:themeElements><a:clrScheme name="Light"><a:dk1><a:srgbClr val="1F2937"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="374151"/></a:dk2><a:lt2><a:srgbClr val="F5F5F4"/></a:lt2><a:accent1><a:srgbClr val="B45309"/></a:accent1><a:accent2><a:srgbClr val="1D4ED8"/></a:accent2><a:accent3><a:srgbClr val="047857"/></a:accent3><a:accent4><a:srgbClr val="B91C1C"/></a:accent4><a:accent5><a:srgbClr val="6D28D9"/></a:accent5><a:accent6><a:srgbClr val="0E7490"/></a:accent6><a:hlink><a:srgbClr val="1D4ED8"/></a:hlink><a:folHlink><a:srgbClr val="6D28D9"/></a:folHlink></a:clrScheme><a:fmtScheme name="Plain"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst><a:lnStyleLst><a:ln><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme><a:fontScheme name="Plain"><a:majorFont><a:latin typeface="Calibri"/></a:majorFont><a:minorFont><a:latin typeface="Calibri"/></a:minorFont></a:fontScheme></a:themeElements></a:theme>"""

SLIDE_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/></Relationships>"""

GEOM = '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'


def _textbox(shape_id: int, name: str, placeholder: str, x: int, y: int, cx: int, cy: int,
             paragraphs: list[tuple[str, int, bool]], lang: str = "en-US", alt: str = "") -> str:
    """A text box shape; paragraphs are (text, size in 100ths of a point, bold)."""
    runs = []
    for text, size, bold in paragraphs:
        runs.append(
            f"<a:p><a:pPr><a:buChar char=\"â€¢\"/></a:pPr>"
            f"<a:r><a:rPr lang=\"{lang}\" sz=\"{size}\" dirty=\"0\"{' b=\"1\"' if bold else ''}/>"
            f"<a:t>{escape(text)}</a:t></a:r></a:p>"
        )
    body = "".join(runs)
    return (
        f"<p:sp><p:nvSpPr><p:cNvPr id=\"{shape_id}\" name=\"{name}\" descr=\"{_escape_alt(alt)}\"/><p:cNvSpPr/>"
        f"<p:nvPr>{placeholder}</p:nvPr></p:nvSpPr>"
        f"<p:spPr><a:xfrm><a:off x=\"{x}\" y=\"{y}\"/><a:ext cx=\"{cx}\" cy=\"{cy}\"/></a:xfrm>{GEOM}</p:spPr>"
        f"<p:txBody><a:bodyPr/><a:lstStyle/>{body}</p:txBody></p:sp>"
    )


def _escape_alt(text: str) -> str:
    return escape(" ".join((text or "").split())[:200], {'"': "&quot;"})


def _slide(heading: str, lines: list[str], big: bool = False, lang: str = "en-US") -> str:
    title_size, body_size = (4400, 2400) if big else (3600, 2000)
    bullets = [(line, body_size, False) for line in lines[:MAX_BULLETS]]
    shapes = _textbox(2, "Title", "<p:ph type=\"title\"/>", 685800, 342900 if big else 685800,
                      10801350, 1143000, [(heading, title_size, True)],
                      lang=lang, alt=heading)
    if bullets:
        shapes += _textbox(3, "Content", "<p:ph type=\"body\" idx=\"1\"/>", 685800, 1600200 if big else 1828800,
                           10801350, 4572000, bullets, lang=lang,
                           alt="; ".join(lines[:3]))
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<p:sld xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\" "
        "xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" "
        "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\">"
        "<p:cSld><p:spTree>"
        "<p:nvGrpSpPr><p:cNvPr id=\"1\" name=\"\"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>"
        "<p:grpSpPr><a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"0\" cy=\"0\"/>"
        "<a:chOff x=\"0\" y=\"0\"/><a:chExt cx=\"0\" cy=\"0\"/></a:xfrm></p:grpSpPr>"
        f"{shapes}</p:spTree></p:cSld>"
        "<p:clrMapOvr><a:overrideClrMapping bg1=\"lt1\" tx1=\"dk1\" bg2=\"lt2\" tx2=\"dk2\" "
        "accent1=\"accent1\" accent2=\"accent2\" accent3=\"accent3\" accent4=\"accent4\" "
        "accent5=\"accent5\" accent6=\"accent6\" hlink=\"hlink\" folHlink=\"folHlink\"/>"
        "</p:clrMapOvr></p:sld>"
    )


def parse_sections(text: str) -> list[dict]:
    """Split pasted training text into slides: blocks separated by blank lines.

    Each block's first line is the heading; lines starting with "-", "*" or a
    number become bullets, other lines become one bullet each.
    """
    slides = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        heading, rest = lines[0][:120], lines[1:]
        bullets = []
        for line in rest:
            cleaned = re.sub(r"^([-*â€¢]|\d+[.)])\s+", "", line).strip()
            if cleaned:
                bullets.append(cleaned[:MAX_TEXT])
        slides.append({"heading": heading, "bullets": bullets[:MAX_BULLETS]})
        if len(slides) >= MAX_SLIDES:
            break
    return slides


def build_pptx(title: str, slides: list[dict], lang: str = "en-US") -> bytes:
    """Assemble a .pptx: a title slide plus one slide per section.

    Shapes carry alt text for screen readers and the run language so
    localized decks do not read as the wrong language.
    """
    title = (title or "Training").strip()[:120] or "Training"
    slides = slides[:MAX_SLIDES]
    parts = [{"heading": title, "bullets": ["PharmaLearn training material"], "big": True}]
    for section in slides:
        heading = str(section.get("heading", "Untitled"))[:120] or "Untitled"
        bullets = [str(line)[:MAX_TEXT] for line in section.get("bullets", [])][:MAX_BULLETS]
        parts.append({"heading": heading, "bullets": bullets, "big": False})
    slide_ids = "".join(
        f"<p:sldId id=\"{256 + index}\" r:id=\"rId{index + 2}\"/>"
        for index in range(len(parts))
    )
    overrides = "".join([
        '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>',
        '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>',
        '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>',
        '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>',
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>',
    ] + [
        f'<Override PartName="/ppt/slides/slide{index + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for index in range(len(parts))
    ])
    slide_rels = "".join(
        f"<Relationship Id=\"rId{index + 2}\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide\" Target=\"slides/slide{index + 1}.xml\"/>"
        for index in range(len(parts))
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as package:
        package.writestr("[Content_Types].xml", CONTENT_TYPES.format(overrides=overrides))
        package.writestr("_rels/.rels", ROOT_RELS)
        package.writestr("docProps/core.xml", CORE_XML.format(title=escape(title)))
        package.writestr("docProps/app.xml", APP_XML.format(slides=len(parts)))
        package.writestr("ppt/presentation.xml", PRESENTATION.format(slides=slide_ids))
        package.writestr("ppt/_rels/presentation.xml.rels",
                         PRESENTATION_RELS.format(slides=slide_rels))
        package.writestr("ppt/slideMasters/slideMaster1.xml", MASTER)
        package.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", MASTER_RELS)
        package.writestr("ppt/slideLayouts/slideLayout1.xml", LAYOUT)
        package.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", LAYOUT_RELS)
        package.writestr("ppt/theme/theme1.xml", THEME)
        for index, part in enumerate(parts):
            body = _slide(part["heading"], part["bullets"], big=part["big"], lang=lang)
            package.writestr(f"ppt/slides/slide{index + 1}.xml", body)
            package.writestr(f"ppt/slides/_rels/slide{index + 1}.xml.rels", SLIDE_RELS)
    buffer.seek(0)
    return buffer.getvalue()


def _pdf_escape(text: str) -> str:
    """Make text safe for a PDF literal: backslash and parens, latin-1 only."""
    cleaned = "".join(char if ord(char) < 256 else "?" for char in text)
    return cleaned.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_wrap(text: str, width: int = 88) -> list[str]:
    words, lines, current = text.split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def build_pdf(title: str, sections: list[dict], lang: str = "en-US") -> bytes:
    """Minimal PDF from the same sections as the PPTX: title plus headings and bullets.

    Dependency-free single text flow with one Helvetica family, so the training
    text in Phase 1 (A17) downloads as a readable PDF without a new library.
    Carries a document language and a bookmark outline per section heading so
    assistive technology can navigate it; full PDF/UA tagging stays future work.
    """
    import re as _re
    if not _re.fullmatch(r"[A-Za-z]{2,3}(-[A-Za-z]{2,4})?", lang or ""):
        lang = "en-US"
    title = (title or "Training").strip()[:120] or "Training"
    sections = sections[:MAX_SLIDES]
    pages: list[list[tuple[str, int, str]]] = [[]]
    page_titles: list[str] = [""]
    cursor = [PDF_TOP]

    def add(font: str, size: int, text: str) -> None:
        if cursor[0] < 72:
            pages.append([])
            page_titles.append("")
            cursor[0] = PDF_TOP
        pages[-1].append((font, size, text[:MAX_TEXT]))
        if font == "F2" and not page_titles[-1]:
            page_titles[-1] = text[:120]
        cursor[0] -= size * 1.5

    add("F2", 22, title)
    cursor[0] -= 8
    for section in sections:
        heading = str(section.get("heading", "Untitled"))[:120] or "Untitled"
        cursor[0] -= 4
        for line in _pdf_wrap(heading, 80):
            add("F2", 13, line)
        for bullet in [str(line)[:MAX_TEXT] for line in section.get("bullets", [])][:MAX_BULLETS]:
            for line in _pdf_wrap(f"- {bullet}", 88):
                add("F1", 11, line)
        cursor[0] -= 4

    outlines_at = 5 + 2 * len(pages)
    objects: list[bytes] = []
    objects.append(f"<< /Type /Catalog /Pages 2 0 R /Lang ({lang}) "
                   f"/Outlines {outlines_at} 0 R /MarkInfo << /Marked true >> >>".encode("latin-1"))
    page_refs = " ".join(f"{4 + index * 2} 0 R" for index in range(len(pages)))
    objects.append(f"<< /Type /Pages /Kids [{page_refs}] /Count {len(pages)} >>".encode("latin-1"))
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    for page_lines in pages:
        content_lines = []
        for font, size, text in page_lines:
            y = 0  # placeholder, replaced below with running position
            _ = y
            content_lines.append((font, size, text))
        stream_lines = []
        y = PDF_TOP
        for font, size, text in content_lines:
            stream_lines.append(f"BT /{font} {size} Tf {PDF_MARGIN} {y:.1f} Td ({_pdf_escape(text)}) Tj ET")
            y -= size * 1.5
            if font == "F2" and size == 22:
                y -= 8
        stream = "\n".join(stream_lines).encode("latin-1")
        page_num = len(objects) + 1
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PDF_PAGE_WIDTH} {PDF_PAGE_HEIGHT}] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {page_num + 1} 0 R >>".encode("latin-1")
        )
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1") + stream + b"\nendstream")

    outline_items = []
    for index, heading in enumerate(page_titles):
        label = heading or f"Page {index + 1}"
        outline_items.append(
            f"<< /Title ({_pdf_escape(label)}) /Parent {outlines_at} 0 R "
            f"/Dest [{5 + index * 2} 0 R /Fit] >>".encode("latin-1"))
    objects.append(
        f"<< /Type /Outlines /First {outlines_at + 1 if outline_items else 0} 0 R "
        f"/Last {outlines_at + len(outline_items)} 0 R "
        f"/Count {len(outline_items)} >>".encode("latin-1"))
    objects.extend(outline_items)
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{index} 0 obj\n".encode("latin-1") + body + b"\nendobj\n")
    xref_at = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    out.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.write(f"{offset:010d} 00000 n \n".encode("latin-1"))
    out.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF".encode("latin-1")
    )
    return out.getvalue()


NARRATION_CHUNK_CHARS = 180
NARRATION_WPM = 140
NARRATION_WPM_MIN, NARRATION_WPM_MAX = 80, 300
_CLAUSE_SPLIT = re.compile(r"\s*[,;:\u2014\u2013]\s*")


def _narration_chunks(texts: list[str], chunk_chars: int = NARRATION_CHUNK_CHARS) -> list[str]:
    """Split speakable texts into short chunks the browser can voice one by one.

    Clause-first: split on clause boundaries, then greedily merge clauses up to
    the character budget, so a chunk never starts mid-clause and timing stays
    honest. Over-long clauses fall back to word packing.
    """
    clauses: list[str] = []
    for text in texts:
        parts = [part.strip() for part in _CLAUSE_SPLIT.split(text) if part.strip()]
        clauses.extend(parts or ([text.strip()] if text.strip() else []))
    chunks, current = [], ""
    for clause in clauses:
        words = clause.split()
        if len(clause) > chunk_chars:
            if current:
                chunks.append(current)
                current = ""
            piece = ""
            for word in words:
                candidate = f"{piece} {word}".strip()
                if len(candidate) <= chunk_chars:
                    piece = candidate
                else:
                    if piece:
                        chunks.append(piece)
                    piece = word
            if piece:
                chunks.append(piece)
            continue
        candidate = f"{current} {clause}".strip()
        if len(candidate) <= chunk_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = clause
    if current:
        chunks.append(current)
    return chunks


def build_narration(title: str, sections: list[dict], wpm: int = NARRATION_WPM,
                    chunk_chars: int = NARRATION_CHUNK_CHARS) -> dict:
    """Full training read-through as speakable chunks with timing (A2, Phase 1).

    No audio bytes are rendered server-side: the browser voices these chunks
    with speech synthesis, so nothing leaves the device. Rate is adjustable
    but never faster-only: complex labels are misheard at speed, so the default
    sits below 150 wpm and callers pick a rate for their audience.
    """
    if not NARRATION_WPM_MIN <= wpm <= NARRATION_WPM_MAX:
        raise ValueError(f"wpm must be between {NARRATION_WPM_MIN} and {NARRATION_WPM_MAX}")
    if not 60 <= chunk_chars <= 500:
        raise ValueError("chunk_chars must be between 60 and 500")
    title = (title or "Training").strip()[:120] or "Training"
    sections = sections[:MAX_SLIDES]
    texts = [title]
    for section in sections:
        heading = str(section.get("heading", "")).strip()
        if heading:
            texts.append(heading)
        texts.extend(str(line).strip() for line in section.get("bullets", []) if str(line).strip())
    chunks = []
    for index, text in enumerate(_narration_chunks(texts, chunk_chars), start=1):
        words = len(text.split())
        seconds = max(1.0, round(words / (wpm / 60), 1))
        chunks.append({"id": f"n{index}", "text": text, "words": words, "seconds": seconds})
    total_words = sum(chunk["words"] for chunk in chunks)
    total_seconds = round(sum(chunk["seconds"] for chunk in chunks), 1)
    return {"title": title, "chunks": chunks, "total_words": total_words, "total_seconds": total_seconds}
