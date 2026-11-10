"""FSRS-lite scheduling: forgetting curve plus documented stability updates."""

from src import fsrs


def test_retrievability_decays_with_time_and_grows_with_stability():
    assert fsrs.retrievability(0, 1.0) == 1.0
    assert fsrs.retrievability(30, 1.0) < fsrs.retrievability(30, 10.0)
    assert fsrs.retrievability(30, 1.0) < fsrs.retrievability(1, 1.0)


def test_correct_recalls_grow_stability_and_misses_shrink_it():
    attempts = [
        {"created_at": "2026-01-01T09:00:00+00:00", "answers": {"q1": 0},
         "_correct": {"q1": 0}},
        {"created_at": "2026-01-08T09:00:00+00:00", "answers": {"q1": 0, "q2": 2},
         "_correct": {"q1": 0, "q2": 1}},
    ]
    plan = fsrs.schedule(attempts, today="2026-01-08")
    assert plan["q1"]["stability"] > 1.0
    assert plan["q2"]["stability"] < 1.0
    assert plan["q2"]["difficulty"] > plan["q1"]["difficulty"]
    assert plan["q2"]["due_in_days"] <= plan["q1"]["due_in_days"]
