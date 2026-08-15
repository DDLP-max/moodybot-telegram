# -*- coding: utf-8 -*-
"""Regression: HIDDEN_TRANSACTION + ESCALATION_PAYOFF capabilities."""
from __future__ import annotations

from capability_detection import (
    detect_escalation_payoff,
    detect_hidden_transaction,
    draft_has_terminal_payoff,
    strip_post_payoff_moral,
)
from response_finalization import build_response_plan, finalize_response


CFO_STORY = (
    "CFO questions expensive cybersecurity vendor. The vendor is secretly run by an employee. "
    "The product is basically nothing. The employee hires an actor. The actor scares the CFO "
    "with jargon. Then the CFO approves more money. Then the employee buys a pontoon boat."
)

CONSULTANT = (
    "Management already knows what it wants to do but hires McKinsey to recommend it."
)

DATING = (
    "Someone repeatedly asks whether their partner is serious despite obvious affection."
)

FIBER = "How do I replace a fiber connector on this patch panel?"

BOAT_FAIL = (
    "First the bilge pump failed. Then the patch job leaked worse. Then the engine flooded. "
    "Then it sank at the dock."
)


def test_cfo_hidden_transaction_and_escalation():
    ht = detect_hidden_transaction(CFO_STORY)
    ep = detect_escalation_payoff(CFO_STORY)
    assert ht.active
    assert ht.confidence >= 0.75
    assert ht.actual_transaction
    assert "risk" in ht.actual_transaction.lower() or "blame" in ht.actual_transaction.lower()
    assert ep.active
    assert ep.concrete_payoff_hint and "pontoon" in ep.concrete_payoff_hint.lower()

    plan = build_response_plan(CFO_STORY, channel="telegram", mode="dynamic")
    assert plan.hidden_transaction is True
    assert plan.escalation_payoff is True

    body = (
        "They weren't buying cybersecurity.\n\n"
        "They were buying somebody else to blame if it failed.\n\n"
        "I just used the new budget increase to buy a pontoon boat."
    )
    result = finalize_response(body, CFO_STORY, plan, channel="telegram", mode="dynamic")
    assert result.diagnostics.get("payoff_is_terminal") == "true"
    assert "pontoon" in result.text.lower()
    assert "that's the lesson" not in result.text.lower()
    assert "sometimes life" not in result.text.lower()
    # No recognition/moral append
    assert not result.text.rstrip().endswith("?")


def test_consultant_cover_not_expense_lecture():
    ht = detect_hidden_transaction(CONSULTANT)
    assert ht.active
    assert ht.actual_transaction
    blob = ht.actual_transaction.lower()
    assert any(k in blob for k in ("cover", "blame", "validation", "letterhead"))
    assert "expensive" not in blob or "cover" in blob


def test_dating_permission_inference_band():
    ht = detect_hidden_transaction(DATING)
    assert ht.active
    assert 0.55 <= ht.confidence < 0.85  # cautious inference band
    assert "permission" in (ht.actual_transaction or "").lower() or "defense" in (
        ht.actual_transaction or ""
    ).lower()


def test_fiber_no_cleverness():
    ht = detect_hidden_transaction(FIBER)
    ep = detect_escalation_payoff(FIBER)
    assert ht.active is False
    assert ep.active is False
    plan = build_response_plan(FIBER, channel="telegram", mode="dynamic")
    assert plan.hidden_transaction is False
    assert plan.escalation_payoff is False


def test_boat_sinking_terminal_no_moral():
    ep = detect_escalation_payoff(BOAT_FAIL)
    assert ep.active
    body = (
        "The pump died.\n\n"
        "The patch made it worse.\n\n"
        "The engine took water.\n\n"
        "It sank at the dock."
    )
    assert draft_has_terminal_payoff(body)
    with_moral = body + "\n\nSometimes the thing you're trying to save teaches you to let go."
    stripped, changed = strip_post_payoff_moral(with_moral)
    assert changed
    assert "sometimes" not in stripped.lower()
    assert "dock" in stripped.lower()

    plan = build_response_plan(BOAT_FAIL, channel="telegram", mode="dynamic")
    plan.escalation_payoff = True
    plan.payoff_is_terminal = True
    result = finalize_response(with_moral, BOAT_FAIL, plan, channel="telegram")
    assert "sometimes the thing" not in result.text.lower()
    assert result.diagnostics.get("payoff_is_terminal") == "true"


def test_guidance_injected_when_active():
    from response_finalization import plan_closer_instruction

    plan = build_response_plan(CFO_STORY)
    instr = plan_closer_instruction(plan)
    assert "HIDDEN_TRANSACTION" in instr
    assert "ESCALATION_PAYOFF" in instr


if __name__ == "__main__":
    test_cfo_hidden_transaction_and_escalation()
    print("ok cfo")
    test_consultant_cover_not_expense_lecture()
    print("ok consultant")
    test_dating_permission_inference_band()
    print("ok dating")
    test_fiber_no_cleverness()
    print("ok fiber")
    test_boat_sinking_terminal_no_moral()
    print("ok boat")
    test_guidance_injected_when_active()
    print("ok")
