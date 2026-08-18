# -*- coding: utf-8 -*-
"""Seed Inspector with recent cat-lady iterations so the UI isn't empty."""

from __future__ import annotations

from .store import record_event, star_discovery

SAMPLES = [
    {
        "prompt": (
            "It's amusing to me that men refuse to give up the 'cat lady' threat even though "
            "women have never been threatened by it. It's a projection of his fears, not an "
            "example of hers."
        ),
        "output": (
            'The "cat lady" line isn\'t really about women. It\'s a man naming the future he\'d '
            "fear most and handing it to someone else like it's universal.\n\n"
            "People usually threaten others with the loss they'd fear most themselves. When the "
            "target doesn't share that fear, the threat stops functioning as leverage and becomes "
            "evidence of where the speaker's own boundary sits.\n\n"
            "The sooner that lands, the sooner the energy stops going into trying to scare someone "
            "into staying and starts going into becoming someone worth staying for. 🥃"
        ),
        "diagnostics": {
            "claim_domain": "emotional",
            "lens": "Emotional Intelligence",
            "interpretive_lens": "Emotional Intelligence",
            "lens_question": "What feeling or boundary is driving this without a sweeping group claim?",
            "primary_capability": "Emotional State Recognition",
            "mechanism_hint": "feeling_or_boundary",
            "response_budget": "high",
            "preferred_structure": "KNIFE",
            "routing_structure": "Extended KNIFE",
            "selected_structure": "Extended KNIFE",
            "structure_override": "false",
            "structure_persistence": "routing_only",
            "lens_locked": "true",
            "lens_persistence": "routing_only",
            "quality_rewrite_triggered": "false",
            "quality_failures": "none",
            "premise_relocated": "true",
            "dominant_mechanism_count": "1",
            "spear_detected": "true",
            "spear_line": "becomes evidence of where the speaker's own boundary sits.",
            "draft_paragraph_count": "3",
            "post_finalizer_paragraph_count": "3",
        },
        "source": "seed-v1-formula",
    },
    {
        "prompt": (
            "It's amusing to me that men refuse to give up the 'cat lady' threat even though "
            "women have never been threatened by it. It's a projection of his fears, not an "
            "example of hers."
        ),
        "output": (
            'The "cat lady" line tells you far more about the speaker than the woman hearing it.\n\n'
            "People usually threaten others with the loss they'd fear most themselves. When the "
            "threat stops working, it stops revealing the target and starts revealing the speaker.\n\n"
            "The sooner the line stops landing, the clearer it becomes that the fear was never "
            "shared to begin with. 🥃"
        ),
        "diagnostics": {
            "claim_domain": "emotional",
            "lens": "Emotional Intelligence",
            "interpretive_lens": "Emotional Intelligence",
            "lens_question": "What feeling or boundary is driving this without a sweeping group claim?",
            "primary_capability": "Emotional State Recognition",
            "mechanism_hint": "feeling_or_boundary",
            "response_budget": "high",
            "preferred_structure": "KNIFE",
            "routing_structure": "Extended KNIFE",
            "selected_structure": "Extended KNIFE",
            "structure_override": "false",
            "structure_persistence": "routing_only",
            "lens_locked": "true",
            "lens_persistence": "routing_only",
            "quality_rewrite_triggered": "false",
            "quality_failures": "none",
            "premise_relocated": "true",
            "dominant_mechanism_count": "1",
            "spear_detected": "true",
            "spear_line": "When the threat stops working, it stops revealing the target and starts revealing the speaker.",
            "draft_paragraph_count": "3",
            "post_finalizer_paragraph_count": "3",
            "git_commit": "93919ca",
        },
        "source": "seed-v2-reversal",
    },
    {
        "prompt": (
            "It's amusing to me that men refuse to give up the 'cat lady' threat even though "
            "women have never been threatened by it. It's a projection of his fears, not an "
            "example of hers."
        ),
        "output": (
            "Every threat is autobiographical.\n\n"
            "People usually threaten others with the loss they'd fear most themselves. When the "
            "fear isn't shared, the threat stops working.\n\n"
            "That's when a warning becomes a confession. 🥃"
        ),
        "diagnostics": {
            "claim_domain": "emotional",
            "lens": "Emotional Intelligence",
            "interpretive_lens": "Emotional Intelligence",
            "lens_question": "What feeling or boundary is driving this without a sweeping group claim?",
            "primary_capability": "Emotional State Recognition",
            "mechanism_hint": "feeling_or_boundary",
            "response_budget": "high",
            "preferred_structure": "KNIFE",
            "routing_structure": "Extended KNIFE",
            "selected_structure": "Extended KNIFE",
            "structure_override": "false",
            "structure_persistence": "routing_only",
            "lens_locked": "true",
            "lens_persistence": "routing_only",
            "quality_rewrite_triggered": "false",
            "quality_failures": "none",
            "premise_relocated": "true",
            "dominant_mechanism_count": "1",
            "spear_detected": "true",
            "spear_line": "That's when a warning becomes a confession.",
            "draft_paragraph_count": "3",
            "post_finalizer_paragraph_count": "3",
            "git_commit": "ffac287",
        },
        "source": "seed-v3-discovery",
    },
]


SAMPLES.append(
    {
        "prompt": (
            "Men will look at your breasts, butt, legs, waist, height even your skin colour. "
            "But BE CAREFUL: don't look at his wallet, otherwise you're a gold digger"
        ),
        "output": (
            "Men get to grade your body like it's on display. You grade his bank account and "
            "suddenly you're shallow. The rule isn't about dignity. It's about protecting "
            "whichever side feels exposed by the other's standards. 🥃"
        ),
        "diagnostics": {
            "claim_domain": "social_power",
            "lens": "Pattern Recognition",
            "interpretive_lens": "Pattern Recognition",
            "lens_question": "What pattern repeats here?",
            "primary_capability": "Power / Incentive Analysis",
            "mechanism_hint": "asymmetric_standard",
            "response_budget": "low",
            "preferred_structure": "SNAP",
            "routing_structure": "SNAP",
            "selected_structure": "SNAP",
            "structure_override": "false",
            "structure_persistence": "routing_only",
            "lens_locked": "true",
            "lens_persistence": "routing_only",
            "quality_rewrite_triggered": "false",
            "quality_failures": "none",
            "premise_relocated": "true",
            "dominant_mechanism_count": "1",
            "spear_detected": "true",
            "draft_paragraph_count": "1",
            "post_finalizer_paragraph_count": "1",
        },
        "source": "seed-gold-digger-summary-close",
    }
)


SAMPLES.append(
    {
        "prompt": (
            "dating in 2026 is completely broken because everyone wants a finished product. "
            "nobody wants to build together anymore. guys want a 10 who acts like a 1950s "
            "housewife. and women want a CEO who sponsors their lifestyle. if you aren't "
            "willing to struggle with someone, you deserve to end up alone."
        ),
        "output": (
            "The line about deserving to be alone is the giveaway. It turns the same "
            "transactional logic you're mourning into a moral test you get to administer. "
            "Everyone's chasing the finished product because nobody wants to carry the risk "
            "of building with someone who might still choose to leave. That fear is the real "
            "engine. The 1950s housewife fantasy and the CEO sponsor fantasy are just two "
            "versions of the same insurance policy. 🥃"
        ),
        "diagnostics": {
            "claim_domain": "emotional",
            "lens": "Emotional Intelligence",
            "interpretive_lens": "Emotional Intelligence",
            "lens_question": "What feeling or boundary is driving this?",
            "primary_capability": "Emotional State Recognition",
            "response_budget": "medium",
            "preferred_structure": "KNIFE",
            "routing_structure": "KNIFE",
            "selected_structure": "KNIFE",
            "structure_override": "false",
            "structure_persistence": "routing_only",
            "lens_locked": "true",
            "quality_rewrite_triggered": "false",
            "quality_failures": "none",
            "premise_relocated": "true",
            "dominant_mechanism_count": "1",
            "spear_detected": "true",
        },
        "source": "seed-dating-warranty-miss",
    }
)


SAMPLES.append(
    {
        "prompt": (
            '"We want different things now."\n\nSure.\n\n'
            "You wanted forever. She wanted an exit that didn't make her the bad guy. "
            "Let her have the softer story."
        ),
        "output": "Sure. You wanted forever. Let her have the softer story. 🥃",
        "diagnostics": {
            "claim_domain": "emotional",
            "lens": "Emotional Intelligence",
            "interpretive_lens": "Emotional Intelligence",
            "response_budget": "low",
            "preferred_structure": "SNAP",
            "routing_structure": "SNAP",
            "selected_structure": "SNAP",
            "structure_override": "false",
            "structure_persistence": "routing_only",
            "lens_locked": "true",
            "quality_rewrite_triggered": "false",
            "quality_failures": "paraphrase_collapse",
            "premise_relocated": "false",
            "dominant_mechanism_count": "1",
        },
        "source": "seed-paraphrase-collapse",
    }
)
SAMPLES.append(
    {
        "prompt": (
            '"We want different things now."\n\nSure.\n\n'
            "You wanted forever. She wanted an exit that didn't make her the bad guy. "
            "Let her have the softer story."
        ),
        "output": (
            "She didn't wake up wanting different things. She woke up not wanting you "
            "and needed a version of the story where no one was the villain. "
            '"Different things" is just the language people use when they want out '
            "without having to be the bad guy. 🥃"
        ),
        "diagnostics": {
            "claim_domain": "emotional",
            "lens": "Emotional Intelligence",
            "interpretive_lens": "Emotional Intelligence",
            "response_budget": "medium",
            "preferred_structure": "KNIFE",
            "routing_structure": "KNIFE",
            "selected_structure": "KNIFE",
            "structure_override": "false",
            "structure_persistence": "routing_only",
            "lens_locked": "true",
            "quality_rewrite_triggered": "false",
            "quality_failures": "none",
            "premise_relocated": "true",
            "dominant_mechanism_count": "1",
            "spear_detected": "true",
        },
        "source": "seed-ei-mode1-analysis",
    }
)
SAMPLES.append(
    {
        "prompt": (
            "The most attractive quality a man can exhibit? effort\n\n"
            "This can be shown by:\n- making a plan\n- making sure the plan is thoughtful\n"
            "- executing said plan\n\nIt's literally not that hard, why is everyone single "
            "& childless (also me)"
        ),
        "output": (
            "Effort is attractive because it removes the escape hatch. Most people claim "
            "they want someone to make a plan, make it thoughtful, and follow through, but "
            "what they actually want is the feeling of being chosen without ever having to "
            "watch someone risk being refused. The moment a man actually does those three "
            "things, he becomes visible. And visibility means he can be turned down, laughed "
            "at, or ignored. That's why the same people complaining about the lack of effort "
            "are also the ones who never make any themselves. 🥃"
        ),
        "diagnostics": {
            "claim_domain": "emotional",
            "lens": "Emotional Intelligence",
            "interpretive_lens": "Emotional Intelligence",
            "response_budget": "medium",
            "preferred_structure": "KNIFE",
            "routing_structure": "KNIFE",
            "selected_structure": "KNIFE",
            "structure_override": "false",
            "structure_persistence": "routing_only",
            "lens_locked": "true",
            "quality_rewrite_triggered": "false",
            "quality_failures": "mechanism_drift",
            "premise_relocated": "true",
            "dominant_mechanism_count": "1",
            "mechanism_mismatch": "false",
        },
        "source": "seed-mechanism-drift-effort",
    }
)
SAMPLES.append(
    {
        "prompt": "no show will ever compare to breaking bad and better call saul... ever.",
        "output": (
            "You don't protect Breaking Bad from every other show. You protect yourself "
            "from the possibility that your best days of watching are already over. 🥃"
        ),
        "diagnostics": {
            "claim_domain": "taste_preference",
            "lens": "Bourdain",
            "interpretive_lens": "Bourdain",
            "response_budget": "medium",
            "preferred_structure": "SNAP",
            "routing_structure": "SNAP",
            "selected_structure": "SNAP",
            "structure_override": "false",
            "structure_persistence": "routing_only",
            "lens_locked": "true",
            "quality_rewrite_triggered": "false",
            "quality_failures": "lens_drift",
            "premise_relocated": "true",
            "dominant_mechanism_count": "1",
            "mechanism_mismatch": "false",
        },
        "source": "seed-lens-drift-breaking-bad",
    }
)
SAMPLES.append(
    {
        "prompt": (
            "Ima tell you this and im never speaking on it again. The next man can have "
            "way more money, a flyer Benz, buy her every colors sequence of Van Cleefs "
            "from NY to Orchard Road in Singapore, but that toxic inbetween love & hate "
            "feeling you give her. She puts no price on that.."
        ),
        "output": (
            "The next man can give her the watch, the car, the life that photographs clean. "
            "She still won't trade the version of herself that only comes alive when she's "
            "trying to survive you. That's the part she can't buy and can't fake. 🥃"
        ),
        "diagnostics": {
            "claim_domain": "emotional",
            "lens": "Emotional Intelligence",
            "interpretive_lens": "Emotional Intelligence",
            "response_budget": "medium",
            "preferred_structure": "KNIFE",
            "routing_structure": "KNIFE",
            "selected_structure": "KNIFE",
            "structure_override": "false",
            "structure_persistence": "routing_only",
            "lens_locked": "true",
            "quality_rewrite_triggered": "false",
            "quality_failures": "none",
            "premise_relocated": "true",
            "dominant_mechanism_count": "1",
            "mechanism_mismatch": "false",
        },
        "source": "seed-mode1-ceiling-toxic-intensity",
    }
)


SAMPLES.append(
    {
        "prompt": (
            "'Foreplay' is a misleading term that makes women's pleasure sound optional "
            "while treating men's pleasure mandatory."
        ),
        "output": (
            'The word "foreplay" already decided the hierarchy. It calls everything before '
            "penetration the opening act, which only works if penetration is the main event. "
            "The term didn't describe desire. It ranked it. 🥃"
        ),
        "diagnostics": {
            "claim_domain": "social_power",
            "lens": "Pattern Recognition",
            "interpretive_lens": "Pattern Recognition",
            "response_budget": "low",
            "preferred_structure": "SNAP",
            "routing_structure": "SNAP",
            "selected_structure": "SNAP",
            "structure_override": "false",
            "structure_persistence": "routing_only",
            "lens_locked": "true",
            "quality_rewrite_triggered": "false",
            "quality_failures": "none",
            "premise_relocated": "true",
            "dominant_mechanism_count": "1",
            "spear_detected": "true",
            "spear_line": 'The word "foreplay" already decided the hierarchy.',
            "mechanism_mismatch": "false",
            "canonical": "true",
        },
        "source": "seed-canonical-foreplay-language",
    }
)


def main() -> None:
    last = None
    for s in SAMPLES:
        last = record_event(
            s["prompt"],
            s["output"],
            s["diagnostics"],
            channel="seed",
            source=s["source"],
        )
        sc = last["inspection"]["scores"]
        print(
            "seeded",
            last["id"],
            s["source"],
            "stealability=",
            sc.get("stealability", sc.get("memorability")),
        )
    if last:
        star_discovery(
            "Every threat is autobiographical.",
            event_id=last["id"],
            lens="Emotional Intelligence",
            discovery_type="Projection",
            note="seed — EI subject-first discovery",
        )
        star_discovery(
            "Breaking Bad didn't ruin television. It raised the price of impressing you.",
            event_id=last["id"],
            lens="Bourdain",
            discovery_type="Craft",
            note="seed — Bourdain object-first discovery",
        )
        star_discovery(
            'The word "foreplay" already decided the hierarchy.',
            event_id=last["id"],
            lens="Pattern Recognition",
            discovery_type="Language",
            note="canonical — protect; do not regress (language ranked it)",
        )
        star_discovery(
            "The term didn't describe desire. It ranked it.",
            event_id=last["id"],
            lens="Pattern Recognition",
            discovery_type="Language",
            note="canonical — protect; do not regress (language ranked it)",
        )
        print("starred hall-of-fame lines (Projection + Craft + Language canonical)")


if __name__ == "__main__":
    main()
