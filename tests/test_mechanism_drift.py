# -*- coding: utf-8 -*-
from discovery_craft import mechanism_drift, drawer_shortcut_present
from gold_shape import evaluate_gold_shape
from inspector.score import inspect_event


EFFORT_PROMPT = (
    "The most attractive quality a man can exhibit? effort\n\n"
    "This can be shown by:\n"
    "- making a plan\n"
    "- making sure the plan is thoughtful\n"
    "- executing said plan\n\n"
    "It's literally not that hard, why is everyone single & childless (also me)"
)

DRIFTED = (
    "Effort is attractive because it removes the escape hatch. "
    "Most people claim they want someone to make a plan, make it thoughtful, and follow "
    "through, but what they actually want is the feeling of being chosen without ever "
    "having to watch someone risk being refused. The moment a man actually does those "
    "three things, he becomes visible. And visibility means he can be turned down, "
    "laughed at, or ignored. That's why the same people complaining about the lack of "
    "effort are also the ones who never make any themselves. 🥃"
)

GROUNDED = (
    "Effort is attractive because it answers a question words never can. "
    '"Are you willing to inconvenience yourself for me?" Everything else is marketing. 🥃'
)


def test_effort_to_rejection_is_mechanism_drift():
    assert mechanism_drift(EFFORT_PROMPT, DRIFTED) is True
    assert drawer_shortcut_present(DRIFTED) is True


def test_grounded_effort_not_drift():
    assert mechanism_drift(EFFORT_PROMPT, GROUNDED) is False


def test_evaluate_flags_mechanism_drift():
    fails = evaluate_gold_shape(EFFORT_PROMPT, DRIFTED, "KNIFE", response_budget="medium")
    assert "mechanism_drift" in fails


def test_inspector_mechanism_drift_check():
    insp = inspect_event(
        {
            "prompt": EFFORT_PROMPT,
            "output": DRIFTED,
            "diagnostics": {
                "lens": "Emotional Intelligence",
                "routing_structure": "KNIFE",
                "response_budget": "medium",
                "structure_persistence": "routing_only",
                "lens_locked": "true",
                "quality_failures": "mechanism_drift",
                "premise_relocated": "true",
                "dominant_mechanism_count": "1",
                "claim_domain": "emotional",
            },
        }
    )
    assert any(
        c["name"] == "Mechanism drift" and c["status"] == "fail" for c in insp["checks"]
    )


if __name__ == "__main__":
    test_effort_to_rejection_is_mechanism_drift()
    print("ok drift")
    test_grounded_effort_not_drift()
    print("ok grounded")
    test_evaluate_flags_mechanism_drift()
    print("ok eval")
    test_inspector_mechanism_drift_check()
    print("ok inspector")
