# -*- coding: utf-8 -*-
"""Sentence-boundary integrity: leading name ID stuck to a new sentence.

Typography only — does not rewrite Moody. Runs the Telegram finalize path.
"""
from postprocessing import polish_sentences
from response_finalization import finalize_response
from surface_qa import detect_surface_issues, repair_name_sentence_boundary, run_surface_qa

USER = (
    "Actors who's accents were so good that you never realized they were from somewhere else?"
)
BROKEN = (
    "Hugh Laurie He crossed the Atlantic with nothing but a throat full of gravel "
    "and a limp that belonged to no country."
)
GOOD = (
    "Hugh Laurie. He crossed the Atlantic with nothing but a throat full of gravel "
    "and a limp that belonged to no country."
)


def _telegram_pre(content: str) -> str:
    """Same pre-finalize transforms as moodybot.py Telegram path (subset that
    can affect punctuation / line joining)."""
    content = polish_sentences(content)
    return content


def test_production_hugh_laurie_he_crossed_via_finalize():
    result = finalize_response(_telegram_pre(BROKEN), USER, channel="telegram")
    assert "Hugh Laurie He crossed" not in result.text
    assert "Hugh Laurie. He crossed" in result.text
    assert result.diagnostics.get("surface_qa_fixed") == "true"


def test_does_not_mutate_name_as_subject():
    for draft in (
        "Hugh Laurie crossed the Atlantic with nothing but a throat full of gravel.",
        "Hugh Laurie was born in England.",
        "Hugh Laurie, however, fooled a generation of American viewers.",
        "Hugh Laurie's American accent fooled millions.",
        "Hugh Laurie, playing House, sounded completely American.",
        "For Hugh Laurie, the accent became part of the disguise.",
    ):
        result = finalize_response(_telegram_pre(draft), USER, channel="telegram")
        body = result.text.replace(" 🥃", "").replace("🥃", "").strip()
        # Voice/whiskey only — the clause itself must be unchanged.
        assert draft.rstrip(".") in body or draft in body


def test_newline_name_then_he_is_repaired():
    raw = (
        "Hugh Laurie\nHe crossed the Atlantic with nothing but a throat full of gravel "
        "and a limp that belonged to no country."
    )
    pre = _telegram_pre(raw)
    assert "Hugh Laurie He crossed" in pre  # polish currently joins the line break
    result = finalize_response(pre, USER, channel="telegram")
    assert "Hugh Laurie He crossed" not in result.text
    assert "Hugh Laurie. He crossed" in result.text


def test_already_correct_period_unchanged():
    result = finalize_response(_telegram_pre(GOOD), USER, channel="telegram")
    assert "Hugh Laurie. He crossed" in result.text
    assert "Hugh Laurie He crossed" not in result.text


def test_helper_is_narrow():
    assert "Hugh Laurie. He crossed" in repair_name_sentence_boundary(BROKEN)
    assert repair_name_sentence_boundary(
        "Hugh Laurie crossed the Atlantic..."
    ) == "Hugh Laurie crossed the Atlantic..."
    kinds = {i.kind for i in detect_surface_issues(BROKEN)}
    assert "name_sentence_boundary" in kinds
    qa = run_surface_qa(BROKEN, auto_repair=True)
    assert qa.fixed
    assert "Hugh Laurie He crossed" not in qa.text


if __name__ == "__main__":
    test_production_hugh_laurie_he_crossed_via_finalize()
    test_does_not_mutate_name_as_subject()
    test_newline_name_then_he_is_repaired()
    test_already_correct_period_unchanged()
    test_helper_is_narrow()
    print("ok")
