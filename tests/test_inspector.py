# -*- coding: utf-8 -*-
from inspector.score import inspect_event
from inspector.store import load_events, record_event, star_discovery


def test_sentence_level_flags_mechanism_summary_close():
    event = {
        "prompt": "gold digger wallet",
        "output": (
            "Men get to grade your body like it's on display. You grade his bank account and "
            "suddenly you're shallow. The rule isn't about dignity. It's about protecting "
            "whichever side feels exposed by the other's standards. 🥃"
        ),
        "diagnostics": {
            "lens": "Pattern Recognition",
            "routing_structure": "SNAP",
            "response_budget": "low",
            "structure_persistence": "routing_only",
            "lens_locked": "true",
            "quality_failures": "none",
            "premise_relocated": "true",
            "dominant_mechanism_count": "1",
            "spear_detected": "true",
            "claim_domain": "social_power",
        },
    }
    insp = inspect_event(event)
    verdicts = [s["verdict"] for s in insp["sentences"]]
    assert "strong" in verdicts
    assert "mechanism_summary" in verdicts
    assert insp["editor"]["last_is_mechanism_summary"] is True
    assert any(c["name"] == "Last line" and c["status"] == "fail" for c in insp["checks"])
    better = inspect_event(
        {
            **event,
            "output": (
                "Men get to grade your body like it's on display. You look at his bank account "
                "and suddenly standards are offensive. Funny how preferences only become immoral "
                "when you're the one being measured. 🥃"
            ),
        }
    )
    assert better["scores"]["stealability"] > insp["scores"]["stealability"]
    assert better["editor"]["last_is_mechanism_summary"] is False


def test_inspect_scores_discovery_higher_than_formula():
    formula = {
        "prompt": "cat lady",
        "output": (
            'The "cat lady" line isn\'t really about women. It\'s projection.\n\n'
            "People usually threaten others with the loss they'd fear most themselves.\n\n"
            "It ends up revealing the speaker. 🥃"
        ),
        "diagnostics": {
            "lens": "Emotional Intelligence",
            "routing_structure": "Extended KNIFE",
            "response_budget": "high",
            "structure_persistence": "routing_only",
            "lens_locked": "true",
            "quality_rewrite_triggered": "false",
            "quality_failures": "none",
            "premise_relocated": "true",
            "dominant_mechanism_count": "1",
            "spear_detected": "true",
            "claim_domain": "emotional",
            "primary_capability": "Emotional State Recognition",
            "lens_question": "What feeling?",
        },
    }
    discovery = {
        **formula,
        "output": (
            "Every threat is autobiographical.\n\n"
            "People usually threaten others with the loss they'd fear most themselves.\n\n"
            "That's when a warning becomes a confession. 🥃"
        ),
    }
    a = inspect_event(formula)
    b = inspect_event(discovery)
    assert b["scores"]["stealability"] > a["scores"]["stealability"]
    assert b["scores"]["stealability"] == b["scores"]["memorability"]
    assert a["editor"]["opening_move"] == "relocation"
    assert any(c["name"] == "Discovery" and c["status"] == "weak" for c in a["checks"])
    assert any(c["name"] == "Discovery" and c["status"] == "pass" for c in b["checks"])


def test_record_and_star(tmp_path, monkeypatch):
    monkeypatch.setenv("MOODYBOT_INSPECTOR_DIR", str(tmp_path))
    # reload paths
    import importlib
    import inspector.store as store

    importlib.reload(store)
    ev = store.record_event(
        "hi",
        "Every threat is autobiographical.\n\nProof.\n\nStop. 🥃",
        {
            "lens": "Emotional Intelligence",
            "routing_structure": "Extended KNIFE",
            "response_budget": "high",
            "structure_persistence": "routing_only",
            "lens_locked": "true",
            "quality_failures": "none",
            "premise_relocated": "true",
            "dominant_mechanism_count": "1",
            "spear_detected": "true",
            "claim_domain": "emotional",
        },
    )
    assert ev["id"]
    assert store.load_events(10)
    store.star_discovery("Every threat is autobiographical.", event_id=ev["id"], lens="EI")
    hall = store.load_hall_of_fame()
    assert hall and hall[0]["line"].startswith("Every threat")


def test_killer_filter_last_line_trap():
    from inspector.telemetry import filter_events

    events = [
        {
            "id": "a",
            "prompt": "gold",
            "output": (
                "Men get to grade your body like it's on display. You grade his bank account and "
                "suddenly you're shallow. The rule isn't about dignity. It's about protecting "
                "whichever side feels exposed by the other's standards. 🥃"
            ),
            "diagnostics": {"lens": "Emotional Intelligence"},
            "source": "live",
        },
        {
            "id": "b",
            "prompt": "gold2",
            "output": (
                "Men get to grade your body like it's on display. Funny how preferences only become "
                "immoral when you're the one being measured. 🥃"
            ),
            "diagnostics": {"lens": "Emotional Intelligence"},
            "source": "live",
        },
    ]
    trapped = filter_events(events, lens="Emotional Intelligence", fail="Last line")
    assert len(trapped) == 1
    assert trapped[0]["id"] == "a"


if __name__ == "__main__":
    test_sentence_level_flags_mechanism_summary_close()
    print("ok sentences")
    test_inspect_scores_discovery_higher_than_formula()
    print("ok scores")
    test_killer_filter_last_line_trap()
    print("ok filter")
