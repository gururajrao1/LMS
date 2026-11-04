"""Training material shared as files: extract Q&A pairs and build quizzes from them.

Everything here is deterministic and extractive — a pair is only emitted when
the document itself asks and answers something, or names a section and explains
it. No model is called, so nothing is invented; a document with no questions in
it yields no pairs, and the caller is told so plainly.
"""

import hashlib
import json
import re
from pathlib import Path

from src.agent import content_path

MAX_PAIRS = 40
MAX_OPTIONS = 4
PASSING_SCORE = 70


def _uploads_root() -> Path:
    return content_path("uploads")


def _upload_dir(upload_id: str) -> Path:
    return _uploads_root() / Path(upload_id).name


def _record(upload_id: str) -> dict:
    path = _upload_dir(upload_id) / "record.json"
    if not path.exists():
        raise FileNotFoundError(f"Unknown upload: {upload_id}")
    return json.loads(path.read_text())


def extract_text(upload_id: str) -> tuple[str, str]:
    """Return (name, plain text) for an upload or staged web source."""
    folder = _upload_dir(upload_id)
    record = _record(upload_id)
    raw = b""
    name = record.get("name", upload_id)
    for candidate in sorted(folder.iterdir()):
        if candidate.name in {"record.json", "qa.json", "quiz.json"}:
            continue
        if candidate.suffix.lower() == ".html" or candidate.name == "fetched.html":
            html = candidate.read_bytes().decode("utf-8", errors="ignore")
            text = re.sub(r"(?s)<(script|style).*?</\1>", " ", html)
            text = re.sub(r"<[^>]+>", " ", text)
            raw += re.sub(r"[ \t]+", " ", text).encode("utf-8") + b"\n"
        else:
            try:
                raw += candidate.read_bytes() + b"\n"
            except OSError:
                continue
    text = raw.decode("utf-8", errors="ignore")
    text = re.sub(r"\r", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return name, text


def _sentences(paragraph: str) -> list[str]:
    return [piece.strip() for piece in re.split(r"(?<=[.!?])\s+", paragraph) if len(piece.strip()) > 20]


def extract_qa(text: str, source: str) -> list[dict]:
    """Pull question/answer pairs out of shared material, nothing invented."""
    lines = [line.strip() for line in text.splitlines()]
    pairs: list[dict] = []

    def add(question: str, answer: str, locator: str) -> None:
        question, answer = question.strip(), answer.strip()
        if len(pairs) >= MAX_PAIRS or len(question) < 8 or len(answer) < 20:
            return
        if any(pair["question"].lower() == question.lower() for pair in pairs):
            return
        pairs.append({"id": f"qa-{len(pairs) + 1}", "question": question,
                      "answer": answer[:1200], "source": source, "locator": locator})

    # Explicit Q/A markers: "Q: ... A: ..." and "Question: ... Answer: ...".
    blocks = re.split(r"\n\s*\n", text)
    for index, block in enumerate(blocks):
        match = re.match(r"(?is)^(?:q|question)\s*[:.\-]\s*(.+?)\n(?:a|answer)\s*[:.\-]\s*(.+)$", block.strip())
        if match:
            add(match.group(1), match.group(2), f"block {index + 1}")

    # A line ending in "?" followed by an answer paragraph.
    for index, line in enumerate(lines):
        if line.endswith("?") and 8 < len(line) < 300 and index + 1 < len(lines) and len(lines[index + 1]) > 20:
            add(line, lines[index + 1], f"line {index + 1}")

    # Headings that explain themselves: short line, substantive paragraph after.
    for index in range(len(lines) - 1):
        head, body = lines[index], lines[index + 1]
        if (head and not head.endswith(("?", ".", ":", ";")) and len(head) < 90
                and len(body) > 60 and not body.endswith("?")):
            add(f"What does the material say about {head.rstrip(':')}?", body, f"line {index + 1}")

    return pairs


def save_qa(upload_id: str) -> dict:
    """Extract Q&A pairs from an upload and keep them beside it."""
    name, text = extract_text(upload_id)
    if not text:
        raise ValueError("No readable text found in this upload")
    pairs = extract_qa(text, name)
    folder = _upload_dir(upload_id)
    (folder / "qa.json").write_text(json.dumps({"upload_id": upload_id, "name": name,
                                                "pairs": pairs}, indent=2) + "\n")
    record = _record(upload_id)
    record["status"] = "processed"
    record["qa_count"] = len(pairs)
    (folder / "record.json").write_text(json.dumps(record, indent=2) + "\n")
    return {"upload_id": upload_id, "name": name, "pairs": pairs}


def load_qa(upload_id: str) -> dict:
    """Read back the stored Q&A pairs for an upload."""
    path = _upload_dir(upload_id) / "qa.json"
    if not path.exists():
        raise FileNotFoundError(f"No extracted Q&A for upload {upload_id}")
    return json.loads(path.read_text())


def build_quiz(upload_id: str, title: str = "") -> dict:
    """Turn extracted Q&A pairs into a scored multiple-choice quiz.

    Distractors are other answers from the same material, so every option is
    grounded in the shared document — including the wrong ones.
    """
    stored = load_qa(upload_id)
    pairs = stored["pairs"]
    if len(pairs) < 2:
        raise ValueError("Extract at least two Q&A pairs before building a quiz")
    answers = [pair["answer"] for pair in pairs]
    questions = []
    for position, pair in enumerate(pairs):
        correct = pair["answer"][:160]
        pool = [answer[:160] for answer in answers if answer[:160] != correct]
        options = [correct]
        for candidate in pool:
            if candidate not in options:
                options.append(candidate)
            if len(options) == MAX_OPTIONS:
                break
        while len(options) < MAX_OPTIONS:
            options.append("Not stated in the material")
        order = sorted(range(len(options)),
                       key=lambda i: hashlib.sha256(f"{pair['id']}:{i}".encode()).hexdigest())
        ordered = [options[i] for i in order]
        questions.append({
            "id": f"uq-{position + 1}",
            "prompt": pair["question"],
            "options": ordered,
            "correct_index": order.index(0),
            "rationale": pair["answer"][:600],
            "citations": [{"title": stored["name"], "locator": pair["locator"]}],
        })
    quiz = {"upload_id": upload_id, "title": title.strip() or f"Quiz: {stored['name']}",
            "passing_score": PASSING_SCORE, "questions": questions}
    (_upload_dir(upload_id) / "quiz.json").write_text(json.dumps(quiz, indent=2) + "\n")
    return quiz


def load_quiz(upload_id: str) -> dict:
    """Read back the built quiz for an upload."""
    path = _upload_dir(upload_id) / "quiz.json"
    if not path.exists():
        raise FileNotFoundError(f"No built quiz for upload {upload_id}")
    return json.loads(path.read_text())
