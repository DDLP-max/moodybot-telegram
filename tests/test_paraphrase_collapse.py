# -*- coding: utf-8 -*-
from discovery_craft import (
    looks_like_discovery,
    paraphrase_collapse,
    prompt_has_discovery,
    response_adds_discovery,
)
from gold_shape import apply_gold_shape_pass, evaluate_gold_shape
from inspector.score import inspect_event


USER = (
    '"We want different things now."\n\n'
    "Sure.\n\n"
    "You wanted forever. She wanted an exit that didn't make her the bad guy. "
    "Let her have the softer story."
)


def test_prison_cell_escapes_frame():
    user = "McDonald's is the best burgers."
    good = "That's like saying a prison cell is just a room. 🥃"
    # Prompt has no discovery-shaped line — collapse gate is N/A / not fail
    assert prompt_has_discovery(user) is False
    assert paraphrase_collapse(user, good) is False
    # Still the craft standard for escaping the frame when the author DID the job
    assert "prison cell" in good.lower()


def test_prompt_discovery_detected():
    assert prompt_has_discovery(USER)
    assert looks_like_discovery(
        "She wanted an exit that didn't make her the bad guy."
    )


def test_abridgment_is_paraphrase_collapse():
    bad = "Sure. You wanted forever. Let her have the softer story. 🥃"
    assert paraphrase_collapse(USER, bad) is True
    assert response_adds_discovery(USER, bad) is False


def test_second_insight_not_collapse():
    good = (
        "Most breakups don't begin when someone wants to leave. "
        "They begin when someone wants to leave without carrying the guilt. 🥃"
    )
    assert paraphrase_collapse(USER, good) is False
    assert response_adds_discovery(USER, good) is True


def test_gold_does_not_delete_discovery_to_abridge():
    # Draft echoes the post including the discovery mid-line
    draft = (
        "Sure. You wanted forever. She wanted an exit that didn't make her the bad guy. "
        "Let her have the softer story."
    )
    # Force a compression path via premise_restatement-like length
    text, report = apply_gold_shape_pass(
        USER,
        draft,
        preferred_structure="SNAP",
        response_budget="low",
    )
    assert "exit that didn't make her the bad guy" in text.lower() or "bad guy" in text.lower()
    # If still collapsed overall, evaluate must flag it — never silently keep bookends only
    if paraphrase_collapse(USER, text):
        assert "paraphrase_collapse" in evaluate_gold_shape(
            USER, text, "SNAP", response_budget="low"
        )


def test_inspector_flags_paraphrase_collapse():
    insp = inspect_event(
        {
            "prompt": USER,
            "output": "Sure. You wanted forever. Let her have the softer story. 🥃",
            "diagnostics": {
                "lens": "Emotional Intelligence",
                "routing_structure": "SNAP",
                "response_budget": "low",
                "structure_persistence": "routing_only",
                "lens_locked": "true",
                "quality_failures": "paraphrase_collapse",
                "premise_relocated": "false",
                "dominant_mechanism_count": "1",
                "claim_domain": "emotional",
            },
        }
    )
    assert any(
        c["name"] == "Paraphrase collapse" and c["status"] == "fail" for c in insp["checks"]
    )


if __name__ == "__main__":
    test_prison_cell_escapes_frame()
    print("ok prison")
    test_prompt_discovery_detected()
    print("ok detect")
    test_abridgment_is_paraphrase_collapse()
    print("ok collapse")
    test_second_insight_not_collapse()
    print("ok second")
    test_gold_does_not_delete_discovery_to_abridge()
    print("ok gold")
    test_inspector_flags_paraphrase_collapse()
    print("ok inspector")
