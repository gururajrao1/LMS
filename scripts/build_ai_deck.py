"""Build the "Where AI is used" note as a PowerPoint asset.

The note in `docs/WHERE_AI_IS_USED.md` is the source of truth; this renders it as
seven slides for a management audience. Deliberately built locally rather than
through the course pipeline's PowerPoint agent: that one costs API budget and is
tuned for clinical decks, and a governance one-pager needs neither.

python-pptx is pulled in for the run rather than added to the project, so nothing
in `pyproject.toml` changes for a script that is used occasionally:

    uv run --with python-pptx python scripts/build_ai_deck.py
"""

import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "where-ai-is-used.pptx"

DEEP = RGBColor(0x0C, 0x3D, 0x31)
BRAND = RGBColor(0x05, 0x96, 0x69)
BRAND_DARK = RGBColor(0x04, 0x78, 0x57)
INK = RGBColor(0x1C, 0x19, 0x17)
MUTED = RGBColor(0x57, 0x53, 0x4E)
WASH = RGBColor(0xEC, 0xFD, 0xF5)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)


def _text(frame, runs, size=14, colour=INK, space_after=6, bold_colour=BRAND_DARK):
    """One paragraph per row; a leading `**bold**` segment is emphasised."""
    frame.word_wrap = True
    for index, line in enumerate(runs):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.space_after = Pt(space_after)
        head, _, tail = line.partition("|")
        first = paragraph.add_run()
        first.text = head.strip()
        first.font.bold = bool(tail)
        first.font.size = Pt(size)
        first.font.color.rgb = bold_colour if tail else colour
        if tail:
            rest = paragraph.add_run()
            rest.text = f"  {tail.strip()}"
            rest.font.size = Pt(size)
            rest.font.color.rgb = colour
    return frame


def _blank(deck):
    return deck.slides.add_slide(deck.slide_layouts[6])


def _fill(slide, colour):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = colour


def _box(slide, left, top, width, height):
    shape = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    return shape.text_frame


def _rule(slide, top, colour=BRAND, width=1.1, height=0.055):
    from pptx.enum.shapes import MSO_SHAPE
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.9), Inches(top), Inches(width), Inches(height))
    bar.fill.solid()
    bar.fill.fore_color.rgb = colour
    bar.line.fill.background()
    bar.shadow.inherit = False
    return bar


def title_slide(deck):
    slide = _blank(deck)
    _fill(slide, DEEP)
    _rule(slide, 2.05, BRAND, width=1.4)
    frame = _box(slide, 0.9, 2.35, 11.0, 0.95)
    _text(frame, ["Where AI is used in PharmaLearn"], size=40, colour=WHITE, space_after=10)
    frame.paragraphs[0].runs[0].font.bold = True
    body = _box(slide, 0.9, 3.45, 10.4, 1.0)
    _text(body, [
        "Every place an agent does work — and the places it is deliberately kept out.",
    ], size=17, colour=RGBColor(0xD6, 0xD3, 0xD1))
    foot = _box(slide, 0.9, 6.05, 11.0, 0.5)
    _text(foot, ["Figures describe the Ibrance example course."], size=11,
          colour=RGBColor(0x8A, 0xA5, 0x9C))
    return slide


def content_slide(deck, kicker, heading, rows, note="", size=14, gap=9):
    slide = _blank(deck)
    _fill(slide, WHITE)
    _rule(slide, 0.62)
    kick = _box(slide, 0.9, 0.78, 10.5, 0.35)
    _text(kick, [kicker.upper()], size=11, colour=BRAND_DARK)
    kick.paragraphs[0].runs[0].font.bold = True
    head = _box(slide, 0.9, 1.12, 11.2, 0.7)
    _text(head, [heading], size=26, colour=INK)
    head.paragraphs[0].runs[0].font.bold = True

    body = _box(slide, 0.9, 2.0, 11.3, 4.3)
    _text(body, rows, size=size, space_after=gap)
    if note:
        tail = _box(slide, 0.9, 6.35, 11.3, 0.6)
        _text(tail, [note], size=11.5, colour=MUTED)
    return slide


def statement_slide(deck, kicker, heading, lines):
    """A slide that exists to make one point, so it is given the whole page."""
    slide = _blank(deck)
    _fill(slide, WASH)
    _rule(slide, 0.62)
    kick = _box(slide, 0.9, 0.78, 10.5, 0.35)
    _text(kick, [kicker.upper()], size=11, colour=BRAND_DARK)
    kick.paragraphs[0].runs[0].font.bold = True
    head = _box(slide, 0.9, 1.2, 11.2, 1.0)
    _text(head, [heading], size=28, colour=INK)
    head.paragraphs[0].runs[0].font.bold = True
    body = _box(slide, 0.9, 2.5, 11.3, 3.6)
    _text(body, lines, size=15, space_after=12)
    return slide


def build() -> Path:
    deck = Presentation()
    deck.slide_width, deck.slide_height = Emu(12192000), Emu(6858000)  # 16:9

    title_slide(deck)

    content_slide(
        deck, "The shape of it", "Three stages, then everyday use",
        [
            "Research | 14 agents, one per section of the dossier. Each searches published sources and returns claims with the citation and the exact sentence it came from.",
            "Authoring | 14 agents write the deck, storyboard, FAQ, quiz and three gamified assessment formats — separately for field medical and healthcare professionals.",
            "Checking | 2 agents read the drafted content and challenge anything that overstates the evidence recorded behind it.",
            "In use | 1 agent answers questions from staff and trainees, using only that course's collected claims, and shows its sources.",
        ],
        note="About 740 agent calls build one course for one drug.",
        size=14.5, gap=16)

    content_slide(
        deck, "Research and authoring", "What each agent produces",
        [
            "Section researcher ×14 | Disease background, mechanism, clinical evidence, label, safety, market context, unmet needs, and more.",
            "Dossier builder | Combines the fourteen sections into one master dossier — the single source everything else is written from.",
            "Deck writer ×2 | The slide-by-slide clinical presentation, per audience.",
            "Storyboard writer ×2 | Scene-by-scene narration and on-screen text.",
            "FAQ writer ×2 | The questions a field team actually gets asked, with escalation guidance.",
            "Quiz writer ×2 | The knowledge check, with a rationale for every answer.",
            "Sort board, instruction builder, figure writer ×2 each | The three gamified assessment formats.",
            "Slide designer ×2 | Turns the deck into a finished, branded PowerPoint.",
        ],
        size=13, gap=7)

    content_slide(
        deck, "Checking", "The machine reviews before a person does",
        [
            "Content checker | Reads the learner-facing content and judges whether it overstates the evidence behind it — stronger claims than the source supports, missing qualifiers, breadth beyond the licensed use.",
            "Second-opinion checker | Re-examines the serious findings before any reach a human, so reviewers are not sent to look at noise.",
            "On the example course this raised 109 findings, 7 of them blocking publication.",
        ],
        note="Everything an agent writes carries its citations forward.",
        size=15, gap=16)

    statement_slide(
        deck, "The shorter list, and the more important one", "Where AI is deliberately not used",
        [
            "Quote verification | Whether a quoted sentence really appears in the source is settled by matching text against the stored file. No model, no variability. Five of the seven blocking findings came from here.",
            "Citation traceability | Whether a citation points at a document we hold is a lookup, not an opinion.",
            "Coverage | Measured against a required-topic list a medical education lead can edit.",
            "Scores, uplift and certificates | Arithmetic on recorded answers.",
            "Schedules and programme status | Derived from the calendar and the cohort every time they are read, so a label can never be stale.",
            "Approval | The checker raises findings. It can never clear one.",
        ])

    content_slide(
        deck, "Guardrails", "The rules the agents work under",
        [
            "Evidence only | An agent writing content is given the dossier and told to use nothing else. An agent answering a question is given the retrieved claims and told the same.",
            "Everything is cited | Content without a citation is flagged automatically.",
            "Nothing self-approves | The machine triages; a named person decides, and any override is recorded against their name.",
            "Spend is capped and logged | Every call is metered against a per-course budget; repeated work is served from cache rather than re-billed.",
        ],
        size=15, gap=16)

    statement_slide(
        deck, "In practice", "What a reviewer actually receives",
        [
            "The agents do the reading, the drafting and the first pass of checking — the volume work.",
            "What arrives at a human is a short queue of specific, evidenced objections.",
            "Each one is clickable through to the claim, the quoted sentence, and the stored source document itself.",
            "Ibrance example course | 14 research sections · 341 citations · 109 findings · 7 blocking.",
        ])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    deck.save(OUT)
    return OUT


if __name__ == "__main__":
    path = build()
    print(f"Wrote {path} ({path.stat().st_size / 1024:.0f} KB, {len(Presentation(path).slides)} slides)")
    sys.exit(0)
