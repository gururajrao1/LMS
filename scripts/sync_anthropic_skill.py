import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "src" / "skills" / "pharmalearn-decks"
CONFIG = ROOT / ".pharmalearn" / "config" / "anthropic_deck_skill.json"
TITLE = "PharmaLearn Training Decks"


def upload_files():
    paths = [SKILL / "SKILL.md", *sorted((SKILL / "assets").glob("*.pptx"))]
    return [
        (f"{SKILL.name}/{path.relative_to(SKILL)}", path.resolve().read_bytes(), "application/octet-stream")
        for path in paths
    ]


def content_hash(files):
    digest = hashlib.sha256()
    for name, content, _ in files:
        digest.update(name.encode())
        digest.update(content)
    return digest.hexdigest()[:16]


def main():
    load_dotenv(ROOT / ".env")
    files = upload_files()
    fingerprint = content_hash(files)
    current = json.loads(CONFIG.read_text()) if CONFIG.exists() else {}
    client = Anthropic()

    if current.get("hash") == fingerprint:
        client.beta.skills.retrieve(current["id"])
        print(f"Reusing {current['id']} version {current['version']}")
        return

    skill_id = current.get("id")
    if not skill_id:
        existing = next((skill for skill in client.beta.skills.list(limit=100, source="custom") if skill.display_title == TITLE), None)
        skill_id = existing.id if existing else None

    if skill_id:
        result = client.beta.skills.versions.create(skill_id, files=files)
        version = result.version
    else:
        result = client.beta.skills.create(display_title=TITLE, files=files)
        skill_id, version = result.id, result.latest_version

    value = {
        "id": skill_id,
        "version": version,
        "hash": fingerprint,
        "synced_at": datetime.now(UTC).isoformat(),
    }
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(value, indent=2) + "\n")
    print(f"Configured {skill_id} version {version}")


if __name__ == "__main__":
    main()
