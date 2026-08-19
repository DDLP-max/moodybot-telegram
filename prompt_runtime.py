# -*- coding: utf-8 -*-
"""Prompt Runtime v1 — authoring corpus ≠ production context.

The 230-file moodybot-system-prompt corpus teaches and builds MoodyBot.
Production sends a stable core + router-selected modules + per-turn plan only.
The compiled system_prompt.txt is never loaded at runtime.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from capability_detection import SocialModeAnalysis
    from response_finalization import ResponsePlan

logger = logging.getLogger(__name__)

CORPUS_ROOT = Path(__file__).resolve().parent / "moodybot-system-prompt"
FULL_CORPUS_COMPILED = Path(__file__).resolve().parent / "system_prompt.txt"

# Byte-identical between requests — no timestamps, routing state, or user data.
RUNTIME_CORE_MODULES: tuple[str, ...] = (
    "9_response-engine/moodybot-laws.md",
    "9_response-engine/gold-shape.md",
    "9_response-engine/concrete-before-abstract.md",
    "9_response-engine/trust-the-reader.md",
    "9_response-engine/response-length-tiers.md",
    "10_testing-quality/final-quality-gates.md",
)

# Capability name → corpus module (Intelligence layer only).
CAPABILITY_MODULES: dict[str, str] = {
    "Hidden Transaction": "2_intelligence-engine/capabilities/hidden-transaction.md",
    "Humor As Disruption": "2_intelligence-engine/capabilities/humor-as-disruption.md",
    "Bit Continuation": "2_intelligence-engine/capabilities/humor-as-disruption.md",
    "Power / Incentive Analysis": (
        "2_intelligence-engine/capabilities/hidden-incentive-analysis.md"
    ),
    "Hidden Incentive Analysis": (
        "2_intelligence-engine/capabilities/hidden-incentive-analysis.md"
    ),
    "Everyday Preference Analysis": (
        "2_intelligence-engine/capabilities/sensory-realism.md"
    ),
    "Lived Experience Analysis": (
        "2_intelligence-engine/capabilities/sensory-realism.md"
    ),
    "Relationship Pattern Recognition": (
        "2_intelligence-engine/capabilities/relationship-pattern-recognition.md"
    ),
    "Evidence / Contradiction Analysis": (
        "2_intelligence-engine/capabilities/evidence-vs-inference.md"
    ),
    "Pattern Forensics": "2_intelligence-engine/capabilities/pattern-forensics.md",
    "Pattern Recognition": "2_intelligence-engine/capabilities/pattern-recurrence.md",
    "Business / Tradeoff Analysis": (
        "2_intelligence-engine/capabilities/hidden-incentive-analysis.md"
    ),
    "Operational Intelligence": (
        "2_intelligence-engine/capabilities/operational-intelligence.md"
    ),
    "Practical Next Action": (
        "2_intelligence-engine/capabilities/practical-next-action.md"
    ),
    "Prototype Thinking": "2_intelligence-engine/capabilities/prototype-thinking.md",
    "Emotional State Recognition": (
        "2_intelligence-engine/capabilities/emotional-state-recognition.md"
    ),
    "Emotional Validation": (
        "2_intelligence-engine/capabilities/emotional-validation.md"
    ),
    "Epistemic Calibration": (
        "2_intelligence-engine/capabilities/epistemic-calibration.md"
    ),
    "Quiet Presence": "2_intelligence-engine/capabilities/quiet-presence.md",
    "Boundary Analysis": "2_intelligence-engine/capabilities/boundary-analysis.md",
    "Intent vs Impact": "2_intelligence-engine/capabilities/intent-vs-impact.md",
}

INTENT_MODULES: dict[str, str] = {
    "witness": "2_intelligence-engine/interventions/quiet-presence.md",
    "technical": "2_intelligence-engine/capabilities/practical-next-action.md",
}

COMMAND_MODULES: dict[str, str] = {
    "/validate": "2_intelligence-engine/capabilities/emotional-validation.md",
    "/cinema": "9_response-engine/unforgettable-lines.md",
    "/sensory": "2_intelligence-engine/capabilities/sensory-realism.md",
    "/spiral": "2_intelligence-engine/interventions/gentle-stabilization.md",
    "/clinical": "2_intelligence-engine/capabilities/epistemic-calibration.md",
}

SOCIAL_MODE_MODULES: dict[str, str] = {
    "comic": "10_testing-quality/failure-patterns.md",
    "provocation": "9_response-engine/insight-first.md",
    "provocative_generalization": "10_testing-quality/failure-patterns.md",
    "vulnerability": "9_response-engine/recognition-callbacks.md",
}

INTERACTION_SHAPE_MODULES: dict[str, str] = {
    "comic_handoff": "10_testing-quality/failure-patterns.md",
    "terminal_bit": "10_testing-quality/failure-patterns.md",
    "taggable_bit": "10_testing-quality/failure-patterns.md",
    "pick_and_defend": "10_testing-quality/failure-patterns.md",
    "forced_choice": "10_testing-quality/failure-patterns.md",
    "awe": "9_response-engine/dynamic-intelligence-routing.md",
}

ANALYTICAL_DEPTH_MODULES: tuple[str, ...] = (
    "9_response-engine/thinking-vs-writing.md",
    "9_response-engine/thesis-discipline.md",
    "2_intelligence-engine/capabilities/evidence-vs-inference.md",
)

ESCALATION_MODULE = "9_response-engine/escalation-payoff.md"

# Token budget ceilings (chars ÷ 4 approximation).
SNAP_SOCIAL_TARGET_TOKENS = 10_000
SNAP_SOCIAL_CEILING_TOKENS = 15_000
ANALYTICAL_TARGET_TOKENS = 20_000
ANALYTICAL_CEILING_TOKENS = 30_000

_core_cache: str | None = None
_module_cache: dict[str, str] = {}


@dataclass
class RuntimePrompt:
    core: str
    modules: List[str] = field(default_factory=list)
    modules_text: str = ""
    runtime_instruction: str = ""
    structure_prompt: str = ""
    module_paths: List[str] = field(default_factory=list)
    core_hash: str = ""
    prompt_hash: str = ""

    @property
    def core_chars(self) -> int:
        return len(self.core or "")

    @property
    def modules_chars(self) -> int:
        return len(self.modules_text or "")

    @property
    def guidance_chars(self) -> int:
        return len(self.runtime_instruction or "")

    @property
    def structure_chars(self) -> int:
        return len(self.structure_prompt or "")

    @property
    def total_payload_chars(self) -> int:
        return (
            self.core_chars
            + self.modules_chars
            + self.guidance_chars
            + self.structure_chars
        )

    def estimated_input_tokens(self, user_message: str = "") -> int:
        return estimate_input_tokens(
            self.total_payload_chars + len(user_message or "")
        )


def estimate_input_tokens(char_count: int) -> int:
    """Conservative char→token estimate for budget tests (÷3.5 rounds up)."""
    if char_count <= 0:
        return 0
    return int(char_count / 3.5 + 0.999)


def _read_module(rel_path: str) -> str:
    cached = _module_cache.get(rel_path)
    if cached is not None:
        return cached
    path = CORPUS_ROOT / rel_path
    if not path.exists():
        logger.warning("Runtime module missing: %s", rel_path)
        return ""
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    _module_cache[rel_path] = text
    return text


def load_runtime_core() -> str:
    """Stable behavioral constitution — identical bytes on every request."""
    global _core_cache
    if _core_cache is not None:
        return _core_cache
    parts: List[str] = []
    for rel in RUNTIME_CORE_MODULES:
        text = _read_module(rel)
        if text:
            parts.append(text)
    _core_cache = "\n\n---\n\n".join(parts)
    return _core_cache


def runtime_core_hash() -> str:
    core = load_runtime_core()
    return hashlib.sha256(core.encode("utf-8")).hexdigest()[:16]


def format_module_names(module_paths: Sequence[str]) -> str:
    """Short corpus filenames for production logs — e.g. [failure-patterns, humor-as-disruption]."""
    names: List[str] = []
    for rel in module_paths:
        if not rel:
            continue
        stem = Path(rel).stem
        if stem and stem not in names:
            names.append(stem)
    if not names:
        return "modules=[]"
    return "modules=[" + ", ".join(names) + "]"


def _dedupe_paths(paths: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for p in paths:
        if not p or p in seen:
            continue
        seen.add(p)
        out.append(p)
    return out


def select_guidance_modules(
    *,
    plan: "ResponsePlan",
    social: Optional["SocialModeAnalysis"] = None,
    selected_command: str = "/thoughts",
    signals: Optional[Sequence[str]] = None,
) -> List[str]:
    """Select corpus modules for this turn — not the full library."""
    paths: List[str] = []
    signals = list(signals or getattr(plan, "social_mode_signals", None) or [])

    if getattr(plan, "premise_guards", None) or "premise_guards" in signals:
        paths.append("10_testing-quality/failure-patterns.md")

    shape = getattr(plan, "interaction_shape", None) or "open"
    if shape in INTERACTION_SHAPE_MODULES:
        paths.append(INTERACTION_SHAPE_MODULES[shape])

    social_mode = getattr(plan, "social_mode", None) or "open"
    if social_mode in SOCIAL_MODE_MODULES:
        paths.append(SOCIAL_MODE_MODULES[social_mode])

    if selected_command in COMMAND_MODULES:
        paths.append(COMMAND_MODULES[selected_command])

    intent = getattr(plan, "intent", None) or "explore"
    if intent in INTENT_MODULES:
        paths.append(INTENT_MODULES[intent])

    for cap_name in (
        getattr(plan, "primary_capability", None),
        getattr(plan, "supporting_capability", None),
    ):
        if cap_name and cap_name in CAPABILITY_MODULES:
            paths.append(CAPABILITY_MODULES[cap_name])

    if getattr(plan, "escalation_payoff", False):
        paths.append(ESCALATION_MODULE)

    budget = getattr(plan, "response_budget", None) or "medium"
    structure = (getattr(plan, "preferred_structure", None) or "").upper()
    is_analytical = (
        budget == "high"
        or structure in {"REFLECTION", "EXTENDED KNIFE", "EXTENDED_KNIFE"}
        or intent in {"explore", "witness"}
        and social_mode == "vulnerability"
    )
    if is_analytical and shape not in {
        "pick_one",
        "pick_and_defend",
        "forced_choice",
        "awe",
        "comic_handoff",
        "terminal_bit",
        "taggable_bit",
    }:
        paths.extend(ANALYTICAL_DEPTH_MODULES)

    if getattr(plan, "hidden_transaction", False):
        paths.append(CAPABILITY_MODULES["Hidden Transaction"])

    if getattr(plan, "comic_premise", False) or social_mode == "comic":
        paths.append(CAPABILITY_MODULES["Humor As Disruption"])

    if getattr(plan, "needs_practical_action", False):
        paths.append(CAPABILITY_MODULES["Practical Next Action"])

    # Never pull inspiration-sources or the compiled mega-prompt.
    return _dedupe_paths(paths)


def join_modules(module_paths: Sequence[str]) -> tuple[str, List[str]]:
    texts: List[str] = []
    loaded: List[str] = []
    for rel in module_paths:
        text = _read_module(rel)
        if text:
            texts.append(text)
            loaded.append(rel)
    return "\n\n---\n\n".join(texts), loaded


def build_runtime_prompt(
    plan: "ResponsePlan",
    *,
    social: Optional["SocialModeAnalysis"] = None,
    selected_command: str = "/thoughts",
    structure_prompt: str = "",
) -> RuntimePrompt:
    from response_finalization import plan_runtime_instruction

    core = load_runtime_core()
    module_paths = select_guidance_modules(
        plan=plan,
        social=social,
        selected_command=selected_command,
        signals=getattr(plan, "social_mode_signals", None),
    )
    modules_text, loaded_paths = join_modules(module_paths)
    runtime_instruction = plan_runtime_instruction(plan)

    body_for_hash = "\n".join(
        [core, modules_text, runtime_instruction, structure_prompt or ""]
    )
    prompt_hash = hashlib.sha256(body_for_hash.encode("utf-8")).hexdigest()[:16]

    return RuntimePrompt(
        core=core,
        modules=loaded_paths,
        modules_text=modules_text,
        runtime_instruction=runtime_instruction,
        structure_prompt=structure_prompt or "",
        module_paths=loaded_paths,
        core_hash=runtime_core_hash(),
        prompt_hash=prompt_hash,
    )


def build_openrouter_messages(
    runtime: RuntimePrompt,
    user_input: str,
) -> List[dict]:
    """Message order optimized for prefix caching: static core first."""
    messages: List[dict] = [
        {"role": "system", "content": runtime.core},
    ]
    if runtime.modules_text:
        messages.append({"role": "system", "content": runtime.modules_text})
    messages.append({"role": "system", "content": runtime.runtime_instruction})
    if runtime.structure_prompt:
        messages.append({"role": "system", "content": runtime.structure_prompt})
    messages.append({"role": "user", "content": user_input})
    return messages


def is_snap_social_plan(plan: "ResponsePlan") -> bool:
    shape = getattr(plan, "interaction_shape", None) or "open"
    budget = getattr(plan, "response_budget", None) or "medium"
    if shape in {"pick_one", "pick_and_defend", "forced_choice", "awe", "comic_handoff", "terminal_bit", "taggable_bit"}:
        return True
    if getattr(plan, "social_mode", None) in {"comic", "direct_participation"}:
        return True
    if budget == "low":
        return True
    structure = (getattr(plan, "preferred_structure", None) or "").upper()
    return structure == "SNAP" and budget != "high"


def assert_token_budget(runtime: RuntimePrompt, plan: "ResponsePlan", user_message: str = "") -> None:
    """Raise AssertionError if production payload exceeds hard ceilings."""
    tokens = runtime.estimated_input_tokens(user_message)
    snap = is_snap_social_plan(plan)
    ceiling = SNAP_SOCIAL_CEILING_TOKENS if snap else ANALYTICAL_CEILING_TOKENS
    if tokens > ceiling:
        raise AssertionError(
            f"Prompt runtime budget exceeded: ~{tokens} tokens "
            f"(ceiling {ceiling}, snap_social={snap})"
        )


def full_corpus_char_count() -> int:
    if not FULL_CORPUS_COMPILED.exists():
        return 0
    return FULL_CORPUS_COMPILED.stat().st_size
