"""FSRS-lite spaced scheduling for reinforce practice.

Full FSRS fits 17+ parameters per learner on hundreds of reviews; a pharma
cohort produces dozens. This lite keeps the FSRS forgetting curve
R(t,S) = (1 + FACTOR*t/S)^DECAY for retrievability and updates stability and
difficulty with small documented steps instead of fitted weights. The schedule
it produces is honest about what it is: more-due-first ordering, not a
memory model claiming precision the data cannot support.
"""

from datetime import date

DECAY = -0.5
FACTOR = 19 / 81


def retrievability(days_since: float, stability: float) -> float:
    """Probability of recall after days_since given stability, 0-1."""
    stability = max(0.1, stability)
    return round((1 + FACTOR * max(0.0, days_since) / stability) ** DECAY, 3)


def _parse_day(value: str | None) -> str | None:
    try:
        from datetime import datetime
        moment = datetime.fromisoformat(value) if value else None
    except ValueError:
        return None
    return moment.date().isoformat() if moment else None


def schedule(attempts: list[dict], today: str | None = None) -> dict:
    """Per-question stability/difficulty/retrievability from past attempts.

    Correct recalls grow stability and ease difficulty; misses shrink
    stability and raise difficulty. New questions start neutral.
    """
    today = today or date.today().isoformat()
    state: dict[str, dict] = {}
    for attempt in sorted(attempts, key=lambda entry: entry.get("created_at", "")):
        day = _parse_day(attempt.get("created_at")) or today
        for qid, chosen in (attempt.get("answers") or {}).items():
            correct = chosen == attempt.get("_correct", {}).get(qid)
            entry = state.setdefault(qid, {"stability": 1.0, "difficulty": 5.0,
                                           "last": day, "correct": 0, "seen": 0})
            entry["seen"] += 1
            entry["last"] = day
            if correct:
                entry["correct"] += 1
                entry["stability"] = round(entry["stability"] * (1.6 - entry["difficulty"] / 20), 2)
                entry["difficulty"] = round(max(1.0, entry["difficulty"] - 0.5), 2)
            else:
                entry["stability"] = round(max(0.2, entry["stability"] * 0.5), 2)
                entry["difficulty"] = round(min(10.0, entry["difficulty"] + 1.0), 2)
    out = {}
    for qid, entry in state.items():
        days_since = (date.fromisoformat(today) - date.fromisoformat(entry["last"])).days
        recall = retrievability(days_since, entry["stability"])
        out[qid] = {**entry, "retrievability": recall,
                    "due_in_days": max(0, round((1 / max(recall, 0.05) - 1) * entry["stability"]))}
    return out
