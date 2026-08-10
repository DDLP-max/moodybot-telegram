# -*- coding: utf-8 -*-
from inspector.log_parser import (
    fingerprint,
    merge_events,
    parse_interaction_log,
    parse_structured_log,
)


def test_parse_interaction_log():
    text = """
[2026-08-01 12:00:00.000000]
User: Men grade bodies but call wallets gold digging
MoodyBot: Men get to grade your body like it's on display. Funny how preferences only become immoral when you're the one being measured. 🥃
"""
    rows = parse_interaction_log(text)
    assert len(rows) == 1
    assert "gold digging" in rows[0]["prompt"]
    assert rows[0]["source"] == "moodybot.log"
    assert rows[0]["meta"]["fingerprint"]


def test_parse_structured_log_with_diagnostics():
    text = """
2026-08-09 13:50:00,001 - INFO - Message received: cat lady threat
2026-08-09 13:50:00,002 - INFO - Selected tone: /thoughts (via auto-route)
2026-08-09 13:50:00,003 - INFO - Response plan: strategy=recognition intent=explain capability=Emotional State Recognition prompt_hash=abc123def456
2026-08-09 13:50:00,010 - INFO - Raw content from API: Every threat is autobiographical.\\n\\nProof follows.
2026-08-09 13:50:00,020 - INFO - Finalization diagnostics: {'lens': 'Emotional Intelligence', 'interpretive_lens': 'Emotional Intelligence', 'claim_domain': 'emotional', 'routing_structure': 'Extended KNIFE', 'response_budget': 'high', 'prompt_hash': 'abc123def456', 'git_commit': 'f51cd8d', 'premise_relocated': 'true', 'spear_detected': 'true', 'dominant_mechanism_count': '1'}
"""
    rows = parse_structured_log(text)
    assert len(rows) == 1
    assert rows[0]["prompt"] == "cat lady threat"
    assert rows[0]["diagnostics"]["lens"] == "Emotional Intelligence"
    assert rows[0]["diagnostics"]["prompt_hash"] == "abc123def456"


def test_merge_dedupes_by_fingerprint():
    a = parse_interaction_log(
        "[2026-08-01 12:00:00]\nUser: hi\nMoodyBot: Every threat is autobiographical. 🥃\n"
    )
    b = [
        {
            **a[0],
            "source": "live",
            "diagnostics": {"lens": "Emotional Intelligence", "prompt_hash": ""},
        }
    ]
    # same prompt/output → one row, richer diagnostics kept
    merged = merge_events(a, b)
    assert len(merged) == 1
    assert merged[0]["diagnostics"].get("lens") == "Emotional Intelligence"
    assert fingerprint("hi", "Every threat is autobiographical. 🥃") == a[0]["meta"]["fingerprint"]


if __name__ == "__main__":
    test_parse_interaction_log()
    test_parse_structured_log_with_diagnostics()
    test_merge_dedupes_by_fingerprint()
    print("ok log_parser")
