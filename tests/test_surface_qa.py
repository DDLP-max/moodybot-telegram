# -*- coding: utf-8 -*-
from postprocessing import polish_sentences
from surface_qa import detect_surface_issues, repair_surface_boundaries, run_surface_qa
from response_finalization import finalize_response


def test_polish_does_not_split_long_and_clause():
    src = (
        "They want the authority to close the door without ever having to stand on the "
        "other side and watch what happens to the man who keeps knocking."
    )
    out = polish_sentences(src)
    assert ". and" not in out
    assert "side and watch" in out


def test_surface_qa_detects_and_repairs_side_and_watch():
    broken = (
        "They want the authority to close the door without ever having to stand on the "
        "other side. and watch what happens to the man who keeps knocking. 🥃"
    )
    issues = detect_surface_issues(broken)
    assert any(i.kind == "sentence_boundary" for i in issues)
    fixed, changed = repair_surface_boundaries(broken)
    assert changed
    assert ". and" not in fixed
    assert "side and watch" in fixed
    assert "🥃" in fixed


def test_run_surface_qa_auto_repair():
    broken = "truth. but only if you stay. 🥃"
    qa = run_surface_qa(broken, auto_repair=True)
    assert qa.fixed
    assert ". but" not in qa.text
    assert "truth but only" in qa.text


def test_finalize_heals_boundary_glitch():
    user = "A lot of modern women want the authority to deny sex indefinitely."
    draft = (
        "The refusal isn't the problem. It's the refusal to admit what the refusal costs "
        "the other person. They want the authority to close the door without ever having "
        "to stand on the other side. and watch what happens to the man who keeps knocking."
    )
    result = finalize_response(draft, user)
    assert ". and" not in result.text
    assert "side and watch" in result.text
    assert result.diagnostics.get("surface_qa_fixed") == "true"


if __name__ == "__main__":
    test_polish_does_not_split_long_and_clause()
    print("ok polish")
    test_surface_qa_detects_and_repairs_side_and_watch()
    print("ok detect/repair")
    test_run_surface_qa_auto_repair()
    print("ok run")
    test_finalize_heals_boundary_glitch()
    print("ok finalize")
