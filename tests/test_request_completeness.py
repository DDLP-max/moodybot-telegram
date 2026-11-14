# -*- coding: utf-8 -*-
"""The answer survives. Style length does not delete a requested count."""
from message_utils import _split_for_telegram
from prompt_runtime import load_runtime_core
from request_contract import (
    completion_gap,
    delivered_item_count,
    parse_user_request,
    request_guidance,
)
from response_finalization import (
    CORE_WRITE_DIRECTIVE,
    build_response_plan,
    finalize_response,
    plan_runtime_instruction,
)
from x_integration.post_length import autonomous_limit, fits_post, weighted_length
from x_integration.reply import _with_post_limit

TEN = (
    "Name ten giant companies that won't survive until 2050. "
    "No mercy, one sentence each on why."
)
SEVEN = (
    "Explain the psychology of destructive relationships. "
    "Give seven distinct reasons people return."
)
OPINION = "What's your opinion of corporate meetings?"
ONE = "One sentence. Why do people lie?"
LONG = (
    "Explain how a business can fail despite increasing revenue. "
    "Give examples and discuss cash flow, margins, and operational risk."
)

NAMES = [
    "General Electric",
    "IBM",
    "Meta",
    "Coca-Cola",
    "Boeing",
    "Intel",
    "Disney",
    "Ford",
    "Exxon",
    "AT&T",
]


def _ten_draft() -> str:
    lines = [
        f"{name} does not get to 2050, in my view, because the model that made it huge is the model that stalls it."
        for name in NAMES
    ]
    return " ".join(lines) + " 🥃"


def test_explicit_requests_are_not_inferred_from_length():
    ten = parse_user_request(TEN)
    assert ten.kind == "counted"
    assert ten.count == 10
    assert ten.unit == "companies"
    assert ten.one_sentence_each is True
    seven = parse_user_request(SEVEN)
    assert seven.kind == "counted" and seven.count == 7 and seven.unit == "reasons"
    assert seven.one_sentence_each is False
    assert parse_user_request(ONE).kind == "one_sentence"
    assert parse_user_request(OPINION).kind == "open"
    long = parse_user_request(LONG)
    assert long.kind == "thorough"
    assert "cash flow" in long.dimensions
    assert "margins" in long.dimensions
    assert "operational risk" in long.dimensions


def test_shared_guidance_obeys_the_request_and_has_no_length_cap():
    guide = plan_runtime_instruction(build_response_plan(TEN, channel="telegram"))
    assert "exactly 10" in guide
    assert "one sentence each" in guide.lower()
    assert "opinions" in guide.lower()
    for banned in ("1–3 sentences", "1-3 sentences", "15–70", "15-70", "280", "weighted characters"):
        assert banned not in guide
    web = plan_runtime_instruction(build_response_plan(TEN, channel="web"))
    assert "exactly 10" in web
    assert "280" not in web
    opinion = request_guidance(OPINION)
    assert "natural length" in opinion
    assert "Do not pad" in opinion
    assert "Exactly one sentence" in request_guidance(ONE)
    seven = request_guidance(SEVEN)
    assert "exactly 7" in seven
    assert "cash flow" in request_guidance(LONG)


def test_finalizer_keeps_a_valid_ten_item_answer():
    draft = _ten_draft()
    result = finalize_response(draft, TEN, channel="telegram")
    text = result.text
    for name in NAMES:
        assert name in text
    assert delivered_item_count(text) >= 10
    assert completion_gap(TEN, text) == ""
    web = finalize_response(draft, TEN, channel="web")
    for name in NAMES:
        assert name in web.text


def test_x_limit_stays_in_the_adapter():
    shared = [{"role": "system", "content": request_guidance(TEN)}, {"role": "user", "content": TEN}]
    prepared = _with_post_limit(shared)
    note = prepared[-2]["content"]
    assert str(autonomous_limit()) in note
    assert "weighted characters" in note
    assert "Do not try to fit ten items" in note
    assert "280" not in shared[0]["content"]
    honest = "A few of these giants are already running on reputation. The rest of that list does not fit here."
    assert fits_post(honest)
    assert weighted_length(honest) <= 280
    too_long = "Word " * 80
    assert not fits_post(too_long)
    assert weighted_length("🔥" * 10) == 20


def test_telegram_split_keeps_every_character():
    body = ("Company line.\n\n" * 400).strip()
    parts = _split_for_telegram(body, limit=3500)
    assert len(parts) > 1
    assert all(len(part) <= 3500 for part in parts)
    assert sum(part.count("Company") for part in parts) == body.count("Company")
    assert sum(part.count("line.") for part in parts) == body.count("line.")


def test_personality_and_continuity_markers_remain():
    core = CORE_WRITE_DIRECTIVE
    assert "🥃" in core
    assert "prison is just a room" in core.lower() or "time sneaks up" in core.lower()
    assert "whose eyes" in core.lower() or "interpretive lens" in core.lower()
    runtime = load_runtime_core().lower()
    assert "whose eyes" in runtime or "interpretive lens" in runtime
    assert "do not drop" in runtime or "requested" in runtime
    assert "15–70" not in runtime
    assert "usually 1–3" not in runtime


if __name__ == "__main__":
    test_explicit_requests_are_not_inferred_from_length()
    print("ok requests")
    test_shared_guidance_obeys_the_request_and_has_no_length_cap()
    print("ok guidance")
    test_finalizer_keeps_a_valid_ten_item_answer()
    print("ok finalizer")
    test_x_limit_stays_in_the_adapter()
    print("ok x")
    test_telegram_split_keeps_every_character()
    print("ok split")
    test_personality_and_continuity_markers_remain()
    print("ok personality")
