"""Minimal PowerPoint builder with no third-party dependency.

Produces a real .pptx (Open Packaging Conventions zip) from a title plus
heading/bullet slides: one title slide and one content slide per section.
Every part needed by the format — content types, relationships, master,
layout, theme and one slide part per slide — is emitted, so PowerPoint,
Keynote and LibreOffice open the file without repair.
"""

import io
import re
import zipfile
from xml.sax.saxutils import escape

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
             paragraphs: list[tuple[str, int, bool]]) -> str:
    """A text box shape; paragraphs are (text, size in 100ths of a point, bold)."""
    runs = []
    for text, size, bold in paragraphs:
        runs.append(
            f"<a:p><a:pPr><a:buChar char=\"•\"/></a:pPr>"
            f"<a:r><a:rPr lang=\"en-US\" sz=\"{size}\" dirty=\"0\"{' b=\"1\"' if bold else ''}/>"
            f"<a:t>{escape(text)}</a:t></a:r></a:p>"
        )
    body = "".join(runs)
    return (
        f"<p:sp><p:nvSpPr><p:cNvPr id=\"{shape_id}\" name=\"{name}\"/><p:cNvSpPr/>"
        f"<p:nvPr>{placeholder}</p:nvPr></p:nvSpPr>"
        f"<p:spPr><a:xfrm><a:off x=\"{x}\" y=\"{y}\"/><a:ext cx=\"{cx}\" cy=\"{cy}\"/></a:xfrm>{GEOM}</p:spPr>"
        f"<p:txBody><a:bodyPr/><a:lstStyle/>{body}</p:txBody></p:sp>"
    )


def _slide(heading: str, lines: list[str], big: bool = False) -> str:
    title_size, body_size = (4400, 2400) if big else (3600, 2000)
    bullets = [(line, body_size, False) for line in lines[:MAX_BULLETS]]
    shapes = _textbox(2, "Title", "<p:ph type=\"title\"/>", 685800, 342900 if big else 685800,
                      10801350, 1143000, [(heading, title_size, True)])
    if bullets:
        shapes += _textbox(3, "Content", "<p:ph type=\"body\" idx=\"1\"/>", 685800, 1600200 if big else 1828800,
                           10801350, 4572000, bullets)
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
            cleaned = re.sub(r"^([-*•]|\d+[.)])\s+", "", line).strip()
            if cleaned:
                bullets.append(cleaned[:MAX_TEXT])
        slides.append({"heading": heading, "bullets": bullets[:MAX_BULLETS]})
        if len(slides) >= MAX_SLIDES:
            break
    return slides


def build_pptx(title: str, slides: list[dict]) -> bytes:
    """Assemble a .pptx: a title slide plus one slide per section."""
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
            body = _slide(part["heading"], part["bullets"], big=part["big"])
            package.writestr(f"ppt/slides/slide{index + 1}.xml", body)
            package.writestr(f"ppt/slides/_rels/slide{index + 1}.xml.rels", SLIDE_RELS)
    buffer.seek(0)
    return buffer.getvalue()
