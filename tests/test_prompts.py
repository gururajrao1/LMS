"""The generation prompts must carry the sentence-level citation rule.

`judge.faithfulness` scores supported cited sentences over cited ones, so a
generated asset with uncited factual sentences fails the check by
construction. This test pins the instruction in the shared prompt prefix
(`common/citations.md`, prepended to every generation stage in `src/agent.py`)
so it cannot be silently dropped.
"""

from src import agent


def _citations_text():
    return (agent.PROMPTS / "common" / "citations.md").read_text()


def test_citation_rules_require_every_factual_sentence_cited():
    text = _citations_text().lower()
    assert "every factual sentence" in text


def test_citation_rules_require_at_least_one_citation_per_sentence():
    text = _citations_text().lower()
    assert "at least one citation" in text


def test_citation_rules_rewrite_or_cut_unsupported_sentences():
    text = _citations_text().lower()
    assert "rewritten or cut" in text
