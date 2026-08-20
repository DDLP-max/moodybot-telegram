# -*- coding: utf-8 -*-
"""Turn diagnostics + prose into an Inspector card (heuristics, not truth)."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from approach_diversity import (
    classify_opening_move,
    ending_is_reveal_speaker,
    first_sentence,
    last_substantive_sentence,
)
from gold_shape import paragraph_count


_SYSTEMS = re.compile(
    r"\b(leverage|boundary|calibration|incentive structure|framework|paradigm|"
    r"narrative contract|systemic)\b",
    re.I,
)
_DISCOVERYISH = re.compile(
    r"^(every |people don'?t |threats |peace |consistency |the mirror |"
    r"the fastest |a threat |funny how |nobody wants |the fantasy |"
    r"everyone says |the line about |most people don'?t |the cleanest |"
    r"you can'?t outbid |chaos has a way )\b|"
    r"\bis autobiographical\b|\bexport (them|fear)\b|"
    r"\bonly become immoral\b|\bwhen you'?re the one being measured\b|"
    r"\bcomes with a warranty\b|\bisn'?t perfection\.? it'?s certainty\b|"
    r"\buncertainty that comes with building\b|"
    r"\bis the giveaway\b|"
    r"\bedit the (relationship|ending)\b|"
    r"\bmessiest rewrites\b|"
    r"\bprison cell is just a room\b|"
    r"\boutbid an addiction\b|"
    r"\bchemical weather\b|"
    r"\bmistakes? intensity for importance\b|"
    r"\bintensity for importance\b|"
    r"\balready decided the hierarchy\b|"
    r"\bdidn'?t describe desire\b|"
    r"\bit ranked it\b|"
    r"\braised the price\b|"
    r"\bdidn'?t ruin television\b|"
    r"\bmakes the safest\b|"
    r"\bdoesn'?t make the best\b|"
    r"\bautobiographical\b",
    re.I,
)
# Competent analysis that summarizes the mechanism instead of landing a discovery
_MECHANISM_SUMMARY = re.compile(
    r"\bisn'?t (really )?about\b.+\bit'?s about\b|"
    r"\bthe (rule|point|issue|problem|move) isn'?t about\b|"
    r"\bwhichever side\b|"
    r"\bprotecting whichever\b|"
    r"\bfeel(?:s|ing)? exposed by\b|"
    r"\bthe other'?s standards\b|"
    r"\bit'?s about protecting\b",
    re.I,
)
# Mode-1 labels / explanations that sound finished but aren't stealable
_GENERIC_MECHANISM = re.compile(
    r"\b(that|this|the) (fear|anxiety|insecurity|need|desire) is the real engine\b|"
    r"\bjust two versions of the same\b|"
    r"\bsame insurance policy\b|"
    r"\binsurance policy\b|"
    r"\bthe real engine\b|"
    r"\bis just the language people use\b|"
    r"\bthe language people use when\b|"
    r"\bcan'?t buy and can'?t fake\b|"
    r"\bshe can'?t buy\b|"
    r"\bthe part she can'?t\b|"
    r"\bno price on that\b",
    re.I,
)
# Names the attachment / dynamic — psychologist Mode 1, not yet the reframe
_MODE1_DYNAMIC = re.compile(
    r"\bcomes alive when\b|"
    r"\btrying to survive you\b|"
    r"\bversion of herself that\b|"
    r"\bonly comes alive\b|"
    r"\bwon'?t trade the version\b",
    re.I,
)
_TOXIC_VALUE_PROMPT = re.compile(
    r"\b(toxic|love.?hate|van cleef|next man|no price|"
    r"money can'?t|chaos|intensity|survive you|"
    r"flyer benz|orchard road)\b",
    re.I,
)
_REFRAME_DISCOVERY = re.compile(
    r"\boutbid\b|\bchemical weather\b|\bintensity for importance\b|"
    r"\bmistakes? intensity\b|\baddiction with stability\b|"
    r"\btrauma .{0,40}(value|love)\b|"
    r"\bpeace feels (suspicious|deeper|safer)\b|"
    r"\bchaos .{0,30}(deeper|valuable|importance)\b",
    re.I,
)
_CONCRETE_SHARP = re.compile(
    r"\b(breasts?|butt|legs?|waist|wallet|bank account|gold digger|"
    r"on display|shallow|grade|measured|immoral|"
    r"photographs clean|watch, the car)\b",
    re.I,
)


def _sentences(text: str) -> List[str]:
    body = re.sub(r"\s*🥃\s*", " ", text or "").strip()
    if not body:
        return []
    parts = re.split(r"(?<=[.!?])\s+", body.replace("\n\n", " ").replace("\n", " "))
    return [s.strip() for s in parts if s and s.strip()]


def _verdict_sentence(
    s: str,
    *,
    is_last: bool,
    is_first: bool = False,
    spear_line: str = "",
) -> Dict[str, str]:
    if spear_line and spear_line.lower()[:40] in s.lower():
        return {
            "text": s,
            "verdict": "spear",
            "note": "the cut — spear line",
        }
    if _MECHANISM_SUMMARY.search(s):
        return {
            "text": s,
            "verdict": "mechanism_summary",
            "note": "restates the mechanism — doesn't deepen it",
        }
    if _GENERIC_MECHANISM.search(s):
        return {
            "text": s,
            "verdict": "generic",
            "note": "labels the mechanism — not an of-course discovery",
        }
    if _DISCOVERYISH.search(s) or (is_last and re.search(r"^funny how\b", s, re.I)):
        return {
            "text": s,
            "verdict": "discovery",
            "note": "stealable — would someone steal this sentence?",
        }
    if _MODE1_DYNAMIC.search(s):
        return {
            "text": s,
            "verdict": "strong",
            "note": "names the dynamic (Mode 1) — psychologist; ask for the reframe",
        }
    if _CONCRETE_SHARP.search(s) and len(s.split()) <= 28:
        return {
            "text": s,
            "verdict": "strong",
            "note": "concrete, spoken, sharpens the premise",
        }
    if not is_first and not is_last and len(s.split()) <= 22:
        return {
            "text": s,
            "verdict": "bridge",
            "note": "carries between beats — keep it short",
        }
    return {"text": s, "verdict": "ok", "note": ""}


def _truthy(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).lower() in {"1", "true", "yes"}


def _int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def inspect_event(event: Dict[str, Any]) -> Dict[str, Any]:
    d = event.get("diagnostics") or {}
    out = event.get("output") or ""
    prompt = event.get("prompt") or ""

    paras = paragraph_count(out)
    words = len(re.findall(r"[A-Za-z']+", out))
    opening = first_sentence(out)
    opening_move = classify_opening_move(out)
    ending = last_substantive_sentence(out)
    spear_line = str(d.get("spear_line") or "")
    sents = _sentences(out)
    sent_rows = [
        _verdict_sentence(
            s,
            is_last=(i == len(sents) - 1),
            is_first=(i == 0),
            spear_line=spear_line,
        )
        for i, s in enumerate(sents)
    ]
    discovery_line = next(
        (r["text"] for r in sent_rows if r["verdict"] == "discovery"),
        opening if _DISCOVERYISH.search(opening) else "",
    )
    last_is_summary = bool(sent_rows) and sent_rows[-1]["verdict"] == "mechanism_summary"
    last_is_generic = bool(sent_rows) and sent_rows[-1]["verdict"] == "generic"
    strong_n = sum(1 for r in sent_rows if r["verdict"] in {"strong", "discovery"})
    generic_n = sum(1 for r in sent_rows if r["verdict"] == "generic")

    checks: List[Dict[str, Any]] = []

    def add(name: str, status: str, why: str = "", examples: List[str] | None = None):
        checks.append(
            {
                "name": name,
                "status": status,  # pass | fail | weak | info
                "why": why,
                "examples": examples or [],
            }
        )

    # Architecture / pipeline from diagnostics
    structure = d.get("routing_structure") or d.get("selected_structure") or d.get("preferred_structure") or ""
    lens = d.get("lens") or d.get("interpretive_lens") or ""
    budget = d.get("response_budget") or ""
    gold_rewrite = _truthy(d.get("quality_rewrite_triggered"))
    mechanisms = _int(d.get("dominant_mechanism_count"), 1)
    premise = _truthy(d.get("premise_relocated"))
    spear = _truthy(d.get("spear_detected"))
    override = _truthy(d.get("structure_override"))
    failures = [f for f in str(d.get("quality_failures") or "none").split(",") if f and f != "none"]

    if structure and not override and d.get("structure_persistence") == "routing_only":
        add("Structure persistence", "pass", f"{structure} held")
    elif override:
        add("Structure persistence", "fail", "structure_override=true")
    else:
        add("Structure persistence", "info", structure or "unknown")

    if _truthy(d.get("lens_locked")) or d.get("lens_persistence") == "routing_only":
        add("Lens persistence", "pass", lens or "locked")
    else:
        add("Lens persistence", "weak", "lens_locked missing")

    expected_paras = {
        "SNAP": (1, 1),
        "KNIFE": (1, 2),
        "Extended KNIFE": (2, 4),
        "REFLECTION": (3, 6),
    }.get(structure, (1, 6))
    if expected_paras[0] <= paras <= expected_paras[1]:
        add("Paragraphs", "pass", f"{paras} (expected {expected_paras[0]}–{expected_paras[1]})")
    else:
        add(
            "Paragraphs",
            "fail",
            f"{paras} paragraphs; {structure or 'shape'} expects {expected_paras[0]}–{expected_paras[1]}",
        )

    if mechanisms <= 1:
        add("Mechanisms", "pass", "1")
    else:
        add("Mechanisms", "fail", f"{mechanisms} competing mechanisms")

    if premise:
        add("Premise relocated", "pass")
    else:
        add("Premise relocated", "weak", "did not relocate the user's premise")

    if spear:
        add("Spear", "pass", (d.get("spear_line") or "")[:160])
    else:
        add("Spear", "weak", "no spear detected")

    if gold_rewrite:
        add("Gold", "info", "rewrite triggered")
    else:
        add("Gold", "pass", "no rewrite — generation stood alone")

    if "over_confirming" in failures or "paragraph_restatement" in failures:
        add(
            "Over-confirming",
            "fail",
            "quality_failures: " + ", ".join(failures),
        )
    else:
        add("Over-confirming", "pass")

    # Trust reader / spokenness / discovery (craft heuristics)
    if _SYSTEMS.search(out):
        hits = sorted({m.group(0).lower() for m in _SYSTEMS.finditer(out)})
        add(
            "Spokenness",
            "fail",
            "systems jargon on the surface",
            examples=[f"leak: {h}" for h in hits[:4]],
        )
    else:
        add("Spokenness", "pass", "would someone say this aloud? — no systems leaks caught")

    # Surface QA — typography integrity (post-Gold)
    from surface_qa import detect_surface_issues

    surface_issues = detect_surface_issues(out)
    qa_diag = [
        f
        for f in str(d.get("surface_qa_failures") or "none").split(",")
        if f and f != "none"
    ]
    if surface_issues or qa_diag:
        examples = []
        for iss in surface_issues[:3]:
            examples.append(f"✗ {iss.span}")
            if iss.suggested:
                examples.append(f"✓ {iss.suggested}")
        if not examples and qa_diag:
            examples = [f"flagged: {x}" for x in qa_diag]
        add(
            "Surface QA",
            "fail",
            "sentence boundary / typography damage — not a writing problem",
            examples=examples,
        )
    elif _truthy(d.get("surface_qa_fixed")):
        add("Surface QA", "pass", "repaired before send")
    else:
        add("Surface QA", "pass", "clean typography")

    # Paraphrase collapse — prompt already had the insight; response added none
    try:
        from discovery_craft import (
            paraphrase_collapse,
            prompt_has_discovery,
            response_adds_discovery,
            discovery_sentences,
        )

        prompt_disc = prompt_has_discovery(prompt)
        added = response_adds_discovery(prompt, out)
        collapsed = paraphrase_collapse(prompt, out) or (
            "paraphrase_collapse" in failures
        )
        if collapsed:
            examples = []
            for s in discovery_sentences(prompt)[:1]:
                examples.append(f"prompt discovery: {s[:140]}")
            examples.append("✓ That's like saying a prison cell is just a room.")
            examples.append(
                "✓ Most breakups don't begin when someone wants to leave. "
                "They begin when someone wants to leave without carrying the guilt."
            )
            examples.append(f"✗ {ending[:140]}")
            add(
                "Paraphrase collapse",
                "fail",
                "preserves the prompt's conclusion instead of contributing a new one — author already did Moody's job; escape the frame",
                examples=examples,
            )
        elif prompt_disc and added:
            add(
                "Paraphrase collapse",
                "pass",
                "prompt had the insight; response escaped the frame / added another",
                examples=[
                    "✓ That's like saying a prison cell is just a room.",
                ],
            )
        elif prompt_disc:
            add(
                "Paraphrase collapse",
                "weak",
                "author may already have done Moody's job — rotate, deepen, challenge, or reveal adjacent; never summarize",
            )
        else:
            add("Paraphrase collapse", "pass", "prompt did not already contain the insight")
    except Exception:
        pass

    # Insight gating — parroting / psychologizing / unsupported depth / runway
    try:
        from capability_detection import detect_comic_premise
        from discovery_craft import (
            parroting,
            psychologizing,
            restates_runway,
            unsupported_depth,
            overperformance,
            rhetorical_explained,
            missed_comic_handoff,
            insight_after_payoff,
            inert_terminal_tag,
            sidesteps_forced_choice,
            reverses_premise_guard,
            uninvited_corrective_analysis,
            corrects_comic_premise,
            engagement_energy_flat,
            engagement_perfume,
            score_engagement_energy,
            authors_unobserved_interior,
            exceeds_contribution_budget,
            competes_with_punchline,
            classify_contribution_budget,
        )

        comic_on = bool(detect_comic_premise(prompt).active) or (
            str(d.get("comic_premise") or "").lower() == "true"
        )
        if parroting(prompt, out) or "parroting" in failures:
            add(
                "Recognition must advance",
                "fail",
                "parroting — after stripping metaphor, the reply knows nothing the user didn't already say. Mirroring cannot be the payload.",
                examples=[
                    "✗ survival mode has become the only operating system left",
                    "✓ reduced social capacity isn't character regression — it's resource allocation",
                ],
            )
        else:
            add(
                "Recognition must advance",
                "pass",
                "reply contributes an inference past the prompt",
            )
        if psychologizing(prompt, out, comic=comic_on) or "psychologizing" in failures:
            add(
                "Psychologizing",
                "fail",
                "converted a joke or complete take into an unwanted diagnosis — depth the premise did not earn",
                examples=[
                    "✗ whether the house still belongs to you",
                    "✓ stay inside the metaphor (footage, plates, timestamps)",
                ],
            )
        else:
            add("Psychologizing", "pass", "did not diagnose a joke")
        if unsupported_depth(prompt, out, comic=comic_on) or "unsupported_depth" in failures:
            add(
                "Unsupported depth",
                "fail",
                "manufactured profundity using a concept that does not exist in the premise — left the bit",
                examples=[
                    "✗ put a leash on something that won't wear one",
                    "✓ Identity theft has gotten incredibly lazy.",
                ],
            )
        else:
            add("Unsupported depth", "pass", "no foreign concept cluster on a comic premise")
        if corrects_comic_premise(prompt, out) or "premise_correction" in failures:
            add(
                "Comic premise inherited",
                "fail",
                "corrected, exposed, or lectured the comic premise instead of inheriting it — correcting the premise is curing it",
                examples=[
                    "✗ You're blaming their tolerance when you were the one being carried.",
                    "✗ Three drops and you're still blaming their tolerance instead of nobody being sober enough to drive.",
                    "✓ You need drinking buddies with forklift certification.",
                    "✓ Three drops is a personnel problem.",
                ],
            )
        elif comic_on:
            add(
                "Comic premise inherited",
                "pass",
                "reasoned inside the comic premise instead of correcting it",
            )
        if reverses_premise_guard(prompt, out) or "premise_reversal" in failures:
            add(
                "Premise guard",
                "fail",
                "smuggled back an interpretation the user explicitly ruled out — don't secretly reverse the premise",
                examples=[
                    "✗ Not bitter. Not lonely. → quiet starts charging interest",
                    "✓ menu isn't worth the prices anymore — consumer behavior, not hidden wound",
                ],
            )
        else:
            add("Premise guard", "pass", "respected explicit premise negations")
        if uninvited_corrective_analysis(prompt, out) or "corrective_analysis" in failures:
            add(
                "Social before correction",
                "fail",
                "uninvited Bench-mode motive prosecution on a casual throwaway generalization",
                examples=[
                    "✗ The payoff in calling most women batshit crazy is that it turns every bad outcome into evidence…",
                    "✓ Most is doing enough work in that sentence to qualify for overtime.",
                ],
            )
        else:
            add("Social before correction", "pass", "did not default to corrective analysis")
        if restates_runway(prompt, out) or "runway_restatement" in failures:
            add(
                "Start where the post stops",
                "fail",
                "summarized the runway the user already built before contributing",
                examples=[
                    "✗ The myth of the passive woman was never about how women actually behaved…",
                    "✓ Women have always pursued. They just used to do it with enough plausible deniability…",
                ],
            )
        else:
            add(
                "Start where the post stops",
                "pass",
                "opens at the inferential edge",
            )
        if overperformance(prompt, out) or "overperformance" in failures:
            add(
                "Overperformance",
                "fail",
                "spent intelligence the interaction didn't ask for — a name-one required a name, not closing narration",
                examples=[
                    "✗ The moment Adam Sandler appears, the frame forgets its own heartbeat…",
                    "✓ Adam Sandler.",
                    "✓ Adam Sandler. I see his face and already know how the next two hours smell.",
                ],
            )
        else:
            add(
                "Overperformance",
                "pass",
                "did not overspend past the question's natural resolution",
            )
        if rhetorical_explained(prompt, out) or "rhetorical_explained" in failures:
            add(
                "Rhetorical obligation",
                "fail",
                "treated a rhetorical how-come as a real why and invented a causal theory",
                examples=[
                    "✗ That's why nobody told you, the ones who know are too busy living inside it…",
                    "✓ The Sopranos doesn't announce itself. It just sits there like a loaded gun on the kitchen table until you finally pick it up.",
                ],
            )
        else:
            add(
                "Rhetorical obligation",
                "pass",
                "did not invent a cause for a rhetorical question",
            )
        if missed_comic_handoff(prompt, out) or "missed_handoff" in failures:
            add(
                "Comic handoff",
                "fail",
                "user left an unresolved contrast slot and Moody started a separate observation",
                examples=[
                    "✗ That's like saying the ideal woman is the one who still thinks Friday night doesn't need a second act.",
                    "✓ …we apparently spent all the R&D money on AI girlfriends.",
                    "✓ They mapped the human genome before solving this.",
                ],
            )
        else:
            add(
                "Comic handoff",
                "pass",
                "did not ignore an open comic slot",
            )
        if insight_after_payoff(prompt, out) or "insight_after_payoff" in failures:
            add(
                "Terminal bit",
                "fail",
                "setup and punchline were complete — reply added insight after the payoff",
                examples=[
                    "✗ The math works until you notice the $2.50 isn't really about the car…",
                    "✓ 🥃",
                    "✓ Fair. 🥃",
                ],
            )
        else:
            add(
                "Terminal bit",
                "pass",
                "did not upgrade a finished comic payoff into philosophy",
            )
        if inert_terminal_tag(prompt, out) or "inert_terminal_tag" in failures:
            add(
                "Terminal contribution",
                "fail",
                "terminal micro-tag was inert — reaction button, not a comic beat",
                examples=[
                    "✗ Fair. 🥃",
                    "✓ Retirement plan denied. Crack the can. 🥃",
                    "✓ Financial literacy has gone too far. 🥃",
                ],
            )
        else:
            add(
                "Terminal contribution",
                "pass",
                "micro-tag compressed or heightened the existing payoff",
            )
        if sidesteps_forced_choice(prompt, out) or "sidestep_forced_choice" in failures:
            add(
                "Play the game",
                "fail",
                "bounded choice prompt answered by sidestepping or inventing an outside option",
                examples=[
                    "✗ I'd sidestep all three and choose freedom.",
                    "✓ Money.",
                    "✓ Gym. At least the disappointment has reps.",
                ],
            )
        else:
            add(
                "Play the game",
                "pass",
                "participated inside a bounded choice frame when required",
            )
        energy = score_engagement_energy(prompt, out)
        energy_on = energy.earned or (
            str(d.get("engagement_energy") or "").lower() == "true"
        )
        if energy_on:
            if engagement_perfume(prompt, out) or "engagement_perfume" in failures:
                add(
                    "Engagement energy",
                    "fail",
                    "perfume — costume voltage instead of heat. Same territory, no teeth.",
                    examples=[
                        "✗ Justice wears the mask of vengeance in the messy visceral hues of reality.",
                        "✓ He was right about Wakanda's hypocrisy; he just confused justice with vengeance.",
                    ],
                )
            elif engagement_energy_flat(prompt, out) or "engagement_flat" in failures:
                add(
                    "Engagement energy",
                    "fail",
                    f"insight landed clean but didn't travel — position {energy.position}, tension {energy.tension}, quotability {energy.quotability}. TAKE A SIDE. CREATE FRICTION. LEAVE A QUOTABLE LINE.",
                    examples=[
                        "✗ The diagnosis was airtight. Only the prescription turned him into the villain the story needed.",
                        "✓ Killmonger. Wakanda spent centuries watching the world bleed… He was right about the hypocrisy; he just confused justice with vengeance.",
                    ],
                )
            else:
                add(
                    "Engagement energy",
                    "pass",
                    f"position {energy.position}, tension {energy.tension}, quotability {energy.quotability} — heat, not perfume",
                    examples=[
                        "✓ He was right about Wakanda's hypocrisy; he just confused justice with vengeance.",
                    ],
                )
        if authors_unobserved_interior(prompt, out) or "authored_interior" in failures:
            add(
                "Object before author",
                "fail",
                "manufactured a hidden truth — motive, guilt, they-knew — that the prompt did not establish. Heat the established object; don't author unobserved interior because it hits harder.",
                examples=[
                    "✗ They call you crazy because now they have to live with the fact that you saw straight through them.",
                    "✗ The crazy label is just what people reach for when they need time to rewrite the story so they were never wrong.",
                    "✓ Everybody loves calling it crazy before it turns into evidence.",
                    "✓ Crazy has a remarkably short shelf life once the receipts show up.",
                    "✗ They're the permanent receipt that someone else is still below them.",
                    "✗ The confusion isn't really about their spreadsheets. It's the quieter dread that the whole point was always just keeping the numbers bigger than the other guy's.",
                    "✓ Turns out infinite money still requires a functioning planet to spend it on.",
                    "✓ You can own every chip in the casino. It still doesn't help when there's no casino left.",
                ],
            )
        else:
            add(
                "Object before author",
                "pass",
                "did not author an unobserved interior to juice the line",
            )
        if (
            exceeds_contribution_budget(prompt, out)
            or competes_with_punchline(prompt, out)
            or "over_contribution" in failures
        ):
            add(
                "Contribution budget",
                "fail",
                "spent more new material than the social moment authorized — capability is not permission",
                examples=[
                    "✗ At this point Claude deserves equity and a parking spot.",
                    "✗ bringing back a fan favorite rebuilds goodwill",
                    "✓ That's usually the part you end up missing.",
                    "✓ Retirement plan denied. Crack the can.",
                ],
            )
        else:
            cb = classify_contribution_budget(prompt)
            add(
                "Contribution budget",
                "pass",
                f"{cb} — did not overspend the social moment",
            )
    except Exception:
        pass

    # Mechanism drift — plausible EI drawer that isn't the prompt's strongest fit
    try:
        from discovery_craft import (
            mechanism_drift,
            mechanism_drift_examples,
            drawer_shortcut_present,
        )

        drifted = mechanism_drift(prompt, out) or ("mechanism_drift" in failures)
        if drifted:
            add(
                "Mechanism drift",
                "fail",
                "plausible emotional mechanism that isn't the strongest fit for THIS prompt — favorite drawer, not prompt spine",
                examples=mechanism_drift_examples(prompt)
                + [f"✗ {ending[:140]}"],
            )
        elif drawer_shortcut_present(out):
            add(
                "Mechanism drift",
                "weak",
                "drawer shortcut present ('what they actually want' / 'the real problem is' / 'it isn't about') — sometimes brilliant, often a steal",
            )
        else:
            add("Mechanism drift", "pass", "no favorite-drawer pivot detected")
    except Exception:
        pass

    # Lens drift — object-first domain answered subject-first (wrong lens ownership)
    try:
        from discovery_craft import (
            early_noun_report,
            lens_drift,
            lens_drift_diagnosis,
            lens_drift_examples,
        )

        domain = str(d.get("claim_domain") or "")
        lens_name = str(d.get("lens") or d.get("interpretive_lens") or "")
        diag = lens_drift_diagnosis(
            prompt, out, claim_domain=domain, lens=lens_name
        )
        early = diag.get("early") or early_noun_report(
            prompt, out, claim_domain=domain, lens=lens_name
        )
        drifted_lens = bool(diag.get("drifted")) or ("lens_drift" in failures)
        if drifted_lens:
            add(
                "Lens drift",
                "fail",
                f"Domain: {diag.get('domain')} · Expected: {diag.get('expected_lens')} · "
                f"Actual: {diag.get('actual_reasoning')} · Drift: {diag.get('drift')} · "
                f"Layer: {diag.get('layer')} · Fix: {diag.get('fix')}",
                examples=lens_drift_examples(prompt)
                + [
                    "✗ You don't protect Breaking Bad… You protect yourself from "
                    "the possibility that your best days of watching are already over."
                ],
            )
        else:
            add(
                "Lens drift",
                "pass",
                "object/subject stance matches lens (no Object→Subject projection)",
            )

        if early and early.get("stance"):
            if early.get("ok"):
                add(
                    "Early nouns",
                    "pass",
                    f"{early.get('stance')} — first sentence keeps the lens's expected open",
                    examples=[early.get("first_sentence", "")[:160]],
                )
            else:
                add(
                    "Early nouns",
                    "fail",
                    early.get("why")
                    or "early nouns violate lens stance (object-first vs subject-first)",
                    examples=[
                        f"first: {early.get('first_sentence', '')[:140]}",
                        f"unexpected: {', '.join(early.get('unexpected_hits') or []) or '—'}",
                        "✓ Breaking Bad / television / craft — not you / yourself / your fear",
                    ],
                )
    except Exception:
        pass

    if last_is_summary or last_is_generic:
        add(
            "Last line",
            "fail",
            "mechanism summary / generic cash-out — routing can be right while distinctiveness fails",
            examples=[
                "✓ Nobody wants a partner who's already finished. They want a future that already comes with a warranty.",
                "✓ The fantasy isn't perfection. It's certainty.",
                f"✗ {ending[:160]}",
            ],
        )
    elif discovery_line and ending == discovery_line:
        add("Last line", "pass", "closes on a discovery", examples=[ending[:160]])
    elif discovery_line:
        add("Last line", "pass", "discovery elsewhere in the reply", examples=[discovery_line[:160]])
    else:
        add("Last line", "weak", "no discovery line — competent but forgettable", examples=[ending[:160]])

    if generic_n and not last_is_generic:
        add(
            "Discovery density",
            "weak",
            "generic mechanism label mid-reply (insurance policy / real engine)",
            examples=[r["text"][:140] for r in sent_rows if r["verdict"] == "generic"][:2],
        )

    if opening_move == "relocation" and not discovery_line:
        add(
            "Discovery",
            "weak",
            "opening explains/relocates instead of surprising",
            examples=[
                "✓ Every threat is autobiographical.",
                f"✗ {opening[:120]}",
            ],
        )
    elif (
        _TOXIC_VALUE_PROMPT.search(prompt)
        and not _REFRAME_DISCOVERY.search(out)
    ):
        has_mode1 = any(_MODE1_DYNAMIC.search(r["text"]) for r in sent_rows)
        add(
            "Discovery",
            "fail" if has_mode1 or strong_n else "weak",
            "Mode 1 ceiling — named the attachment; missed why chaos feels more valuable than peace",
            examples=[
                "✓ You can't outbid an addiction with stability.",
                "✓ Sometimes they miss the chemical weather that came with them.",
                "✓ Your nervous system mistakes intensity for importance.",
                f"✗ {ending[:140]}",
            ],
        )
    elif discovery_line:
        add("Discovery", "pass", "stealable line present", examples=[discovery_line])
    elif strong_n >= 1 and not last_is_summary:
        add("Discovery", "weak", "strong concrete lines, but no discovery close")
    else:
        add("Discovery", "weak", "no clear discovery line detected", examples=[opening[:160]])

    # Mode 1 ceiling as its own teachable check when toxic-value + explain-without-reframe
    if _TOXIC_VALUE_PROMPT.search(prompt) and not _REFRAME_DISCOVERY.search(out):
        add(
            "Mode 1 ceiling",
            "fail",
            "psychologist named the dynamic; writer didn't reframe the claim "
            "(trauma/intensity mistaken for value)",
            examples=[
                "✓ You can't outbid an addiction with stability.",
                "✗ …the version of herself that only comes alive when she's trying to survive you.",
            ],
        )
    elif any(_MODE1_DYNAMIC.search(r["text"]) for r in sent_rows) and not discovery_line:
        add(
            "Mode 1 ceiling",
            "weak",
            "names the dynamic without a stealable reframe",
        )
    else:
        add("Mode 1 ceiling", "pass", "reframe present or not a Mode-1-ceiling prompt")

    if ending_is_reveal_speaker(out) and opening_move in {"relocation", "reversal"}:
        add(
            "Ending variety",
            "weak",
            "lands on 'revealing the speaker' — allowed, becoming formula",
            examples=[ending[:160]],
        )
    elif not last_is_summary:
        add("Ending variety", "pass", ending[:120])

    # Scores 0–10
    architecture = 10
    if override:
        architecture -= 3
    if not (expected_paras[0] <= paras <= expected_paras[1]):
        architecture -= 2
    if gold_rewrite:
        architecture -= 0  # not a failure
    architecture = max(0, min(10, architecture))

    lens_fidelity = 9 if lens else 5
    if _truthy(d.get("mechanism_mismatch")):
        lens_fidelity -= 3
    if "Emotional" in lens and opening_move == "relocation":
        lens_fidelity -= 0
    lens_fidelity = max(0, min(10, lens_fidelity))

    writing = 8
    if _SYSTEMS.search(out):
        writing -= 2
    if "over_confirming" in failures:
        writing -= 2
    if last_is_summary:
        writing -= 1
    if strong_n >= 1:
        writing += 1
    if words > 0 and words < 25 and structure == "Extended KNIFE":
        writing -= 1
    writing = max(0, min(10, writing))

    # Stealability = would someone steal a sentence from this?
    stealability = 6
    if discovery_line:
        stealability = 9
    elif strong_n >= 2 and not last_is_summary:
        stealability = 8
    elif opening_move in {"contradiction", "irony", "reversal", "image"}:
        stealability = 7
    elif opening_move == "relocation":
        stealability = 5
    if last_is_summary:
        stealability -= 2
    if last_is_generic:
        stealability -= 1
    if ending_is_reveal_speaker(out) and opening_move == "relocation":
        stealability -= 1
    # Mode 1 ceiling: named the dynamic, missed the reframe — cap below Hall-of-Fame
    if _TOXIC_VALUE_PROMPT.search(prompt) and not _REFRAME_DISCOVERY.search(out):
        stealability = min(stealability, 7)
    stealability = max(0, min(10, stealability))
    memorability = stealability  # back-compat alias

    pipeline = [
        {"label": "Claim Type", "value": d.get("claim_domain") or "—", "ok": bool(d.get("claim_domain"))},
        {"label": "Lens", "value": lens or "—", "ok": bool(lens)},
        {"label": "Lens Question", "value": (d.get("lens_question") or "—")[:120], "ok": bool(d.get("lens_question"))},
        {"label": "Capability", "value": d.get("primary_capability") or "—", "ok": bool(d.get("primary_capability"))},
        {"label": "Mechanism hint", "value": d.get("mechanism_hint") or "—", "ok": True},
        {"label": "Budget", "value": (budget or "—").title(), "ok": bool(budget)},
        {"label": "Structure", "value": structure or "—", "ok": bool(structure)},
        {
            "label": "Gold",
            "value": "Rewrite" if gold_rewrite else "No rewrite",
            "ok": not gold_rewrite,
        },
    ]

    return {
        "pipeline": pipeline,
        "editor": {
            "paragraphs": paras,
            "words": words,
            "mechanisms": mechanisms,
            "opening_move": opening_move,
            "opening": opening,
            "ending": ending,
            "discovery_line": discovery_line,
            "spear_line": d.get("spear_line") or "",
            "quality_failures": failures,
            "last_is_mechanism_summary": last_is_summary,
            "last_is_generic": last_is_generic,
            "generic_n": generic_n,
        },
        "sentences": sent_rows,
        "checks": checks,
        "scores": {
            "architecture": architecture,
            "lens_fidelity": lens_fidelity,
            "writing": writing,
            "stealability": stealability,
            "memorability": memorability,
        },
    }


def diff_events(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Compare two inspections — what changed between yesterday and today."""
    ia = a.get("inspection") or inspect_event(a)
    ib = b.get("inspection") or inspect_event(b)
    ea, eb = ia.get("editor") or {}, ib.get("editor") or {}
    return {
        "opening_changed": (ea.get("opening") or "") != (eb.get("opening") or ""),
        "opening_a": ea.get("opening"),
        "opening_b": eb.get("opening"),
        "opening_move_a": ea.get("opening_move"),
        "opening_move_b": eb.get("opening_move"),
        "structure_a": (a.get("diagnostics") or {}).get("routing_structure"),
        "structure_b": (b.get("diagnostics") or {}).get("routing_structure"),
        "structure_changed": (a.get("diagnostics") or {}).get("routing_structure")
        != (b.get("diagnostics") or {}).get("routing_structure"),
        "stealability_a": (ia.get("scores") or {}).get("stealability")
        or (ia.get("scores") or {}).get("memorability"),
        "stealability_b": (ib.get("scores") or {}).get("stealability")
        or (ib.get("scores") or {}).get("memorability"),
        "memorability_a": (ia.get("scores") or {}).get("memorability"),
        "memorability_b": (ib.get("scores") or {}).get("memorability"),
        "gold_a": (a.get("diagnostics") or {}).get("quality_rewrite_triggered"),
        "gold_b": (b.get("diagnostics") or {}).get("quality_rewrite_triggered"),
    }


def aggregate_lens_stats(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Per-lens bars (secondary — dashboard leads with today's pages)."""
    buckets: Dict[str, Dict[str, Any]] = {}
    for e in events:
        d = e.get("diagnostics") or {}
        lens = d.get("lens") or d.get("interpretive_lens") or "Unknown"
        insp = e.get("inspection") or inspect_event(e)
        scores = insp.get("scores") or {}
        steal = float(scores.get("stealability") if scores.get("stealability") is not None else scores.get("memorability") or 0)
        b = buckets.setdefault(
            lens,
            {
                "lens": lens,
                "n": 0,
                "stealability": 0.0,
                "memorability": 0.0,
                "writing": 0.0,
                "architecture": 0.0,
                "relocation": 0,
            },
        )
        b["n"] += 1
        b["stealability"] += steal
        b["memorability"] += steal
        b["writing"] += float(scores.get("writing") or 0)
        b["architecture"] += float(scores.get("architecture") or 0)
        if (insp.get("editor") or {}).get("opening_move") == "relocation":
            b["relocation"] += 1
    out = []
    for b in buckets.values():
        n = max(1, b["n"])
        out.append(
            {
                "lens": b["lens"],
                "n": b["n"],
                "stealability": round(b["stealability"] / n, 1),
                "memorability": round(b["memorability"] / n, 1),
                "writing": round(b["writing"] / n, 1),
                "architecture": round(b["architecture"] / n, 1),
                "relocation_share": round(b["relocation"] / n, 2),
            }
        )
    out.sort(key=lambda x: -x["n"])
    return out
