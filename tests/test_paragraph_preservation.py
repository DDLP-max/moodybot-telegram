"""Paragraph cadence is a structural contract — never flatten \\n\\n before send."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gold_shape import apply_gold_shape_pass, paragraph_count
from postprocessing import polish_sentences, strip_prefab_phrases
from response_finalization import finalize_response, build_response_plan
from surface_render import final_surface_render


MULTI = (
    "People reach for the loss that would break them and assume it breaks everyone else.\n\n"
    "The \"cat lady\" line isn't really about women. It's a man naming the future he'd fear "
    "most and handing it to someone else like it's universal.\n\n"
    "The moment it stops landing, repeating it doesn't make it sharper. "
    "It only reveals he never understood what she was afraid of in the first place."
)


def test_polish_sentences_preserves_blank_line_paragraphs():
    out = polish_sentences(MULTI)
    assert paragraph_count(out) == 3
    assert "\n\n" in out


def test_strip_prefab_preserves_blank_line_paragraphs():
    out = strip_prefab_phrases(MULTI)
    assert paragraph_count(out) == 3
    assert "\n\n" in out


def test_editor_preserves_extended_knife_paragraphs():
    out, _ = apply_gold_shape_pass(
        "cat lady threat projection",
        MULTI,
        preferred_structure="KNIFE",
        response_budget="high",
    )
    assert paragraph_count(out) >= 2
    assert "\n\n" in out


def test_finalizer_preserves_paragraphs_for_high_knife():
    cat_lady = (
        "It's amusing to me that men refuse to give up the 'cat lady' threat even though "
        "women have never been threatened by it. It's a projection of his fears, not an "
        "example of hers. The biggest fear for these men is ending up alone so they assume "
        "it's women's biggest fear too, but it's not. There's no female loneliness epidemic "
        "because women don't experience loneliness like men do. Women don't need companionship "
        "in the same way that men do. Women are okay being single because women aren't ever "
        "really 'alone' like single men are. The sooner these men realize that threatening "
        "women with singledom isn't really a threat at all, the sooner they can switch their "
        "focus to becoming a man who women actually want to be in a relationship with instead."
    )
    plan = build_response_plan(cat_lady)
    assert plan.response_budget == "high"
    assert plan.preferred_structure == "KNIFE"
    finalized = finalize_response(MULTI, cat_lady, plan, channel="telegram")
    assert int(finalized.diagnostics["draft_paragraph_count"]) == 3
    assert int(finalized.diagnostics["post_editor_paragraph_count"]) >= 2
    assert int(finalized.diagnostics["post_finalizer_paragraph_count"]) >= 2
    assert paragraph_count(finalized.text) >= 2


def test_surface_render_preserves_paragraphs():
    text, _ = final_surface_render(MULTI)
    assert paragraph_count(text) == 3


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
