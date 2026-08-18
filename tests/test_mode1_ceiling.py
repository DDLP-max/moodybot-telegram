# -*- coding: utf-8 -*-
"""Mode 1 ceiling — names the dynamic, misses the reframe."""

from inspector.score import inspect_event

TOXIC_PROMPT = (
    "Ima tell you this and im never speaking on it again. The next man can have "
    "way more money, a flyer Benz, buy her every colors sequence of Van Cleefs "
    "from NY to Orchard Road in Singapore, but that toxic inbetween love & hate "
    "feeling you give her. She puts no price on that.."
)

MODE1 = (
    "The next man can give her the watch, the car, the life that photographs clean. "
    "She still won't trade the version of herself that only comes alive when she's "
    "trying to survive you. That's the part she can't buy and can't fake. 🥃"
)

MODE2 = (
    "The next man can give her the watch, the car, the life that photographs clean. "
    "You can't outbid an addiction with stability. 🥃"
)


def _checks(insp):
    return {c["name"]: c for c in insp["checks"]}


def test_mode1_ceiling_flags_explain_without_reframe():
    insp = inspect_event(
        {
            "prompt": TOXIC_PROMPT,
            "output": MODE1,
            "diagnostics": {
                "claim_domain": "emotional",
                "lens": "Emotional Intelligence",
                "routing_structure": "KNIFE",
                "structure_persistence": "routing_only",
                "lens_locked": "true",
                "dominant_mechanism_count": "1",
                "premise_relocated": "true",
            },
        }
    )
    c = _checks(insp)
    assert c["Mode 1 ceiling"]["status"] == "fail"
    assert c["Discovery"]["status"] == "fail"
    assert c["Last line"]["status"] == "fail"  # can't buy / can't fake → generic
    assert insp["scores"]["stealability"] <= 7.5

    sents = {r["text"]: r["verdict"] for r in insp["sentences"]}
    assert any(
        "photographs clean" in t and v == "strong" for t, v in sents.items()
    )
    assert any(
        "comes alive" in t and v == "strong" for t, v in sents.items()
    )
    assert any(
        "can't buy" in t.lower() and v == "generic" for t, v in sents.items()
    )


def test_mode2_reframe_passes_ceiling():
    insp = inspect_event(
        {
            "prompt": TOXIC_PROMPT,
            "output": MODE2,
            "diagnostics": {
                "claim_domain": "emotional",
                "lens": "Emotional Intelligence",
                "routing_structure": "KNIFE",
                "structure_persistence": "routing_only",
                "lens_locked": "true",
                "dominant_mechanism_count": "1",
                "premise_relocated": "true",
            },
        }
    )
    c = _checks(insp)
    assert c["Mode 1 ceiling"]["status"] == "pass"
    assert c["Discovery"]["status"] == "pass"
    assert insp["scores"]["stealability"] >= 8


if __name__ == "__main__":
    test_mode1_ceiling_flags_explain_without_reframe()
    test_mode2_reframe_passes_ceiling()
    print("ok")
