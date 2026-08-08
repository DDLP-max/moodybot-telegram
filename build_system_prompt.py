#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced MoodyBot System Prompt Builder
Automatically compiles all markdown files from the modular system prompt directory
Includes recursive scanning for subdirectories (like personas)
Emits assembly diagnostics for finalization-critical modules.
"""

import sys
import hashlib
import json

# Windows consoles often default to CP1252; keep emoji logging readable.
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import pathlib

# Set the root to the current directory (replit folder)
ROOT = pathlib.Path.cwd()
ORDER = [
    "1_emotional-architecture",
    "2_intelligence-engine",
    "3_voice-engine",
    "4_formatting-structure",
    "5_safety-protocols",
    "6_engagement-conversion",
    "7_design-process",
    "8_emotional-modulation",
    "9_response-engine",
    "10_testing-quality",
]

# Appended LAST so enforcement beats earlier engagement goals.
CRITICAL_TAIL = [
    "2_intelligence-engine/capabilities/evidence-vs-inference.md",
    "2_intelligence-engine/capabilities/epistemic-calibration.md",
    "2_intelligence-engine/capabilities/practical-next-action.md",
    "9_response-engine/recognition-callbacks.md",
    "9_response-engine/response-generation-order.md",
    "10_testing-quality/final-quality-gates.md",
]

CRITICAL_NAMES = [
    "epistemic-calibration",
    "evidence-vs-inference",
    "practical-next-action",
    "recognition-callbacks",
    "response-generation-order",
    "final-quality-gates",
]


def _section_label(rel_path: str) -> str:
    return rel_path.replace("\\", "/")


def main() -> None:
    chunks = []
    section_names = []
    seen = set()
    critical_tail_set = {_section_label(ct) for ct in CRITICAL_TAIL}

    for section in ORDER:
        sec = ROOT / "moodybot-system-prompt" / section
        if not sec.exists():
            print(f"⚠️  Section {section} not found, skipping...")
            continue

        print(f"📁 Processing section: {section}")

        for p in sorted(sec.glob("*.md")):
            if p.name.lower() in {"readme.md"}:
                continue
            rel = f"{section}/{p.name}"
            if rel in critical_tail_set:
                continue  # deferred to enforcement tail
            print(f"  📄 Adding: {rel}")
            chunks.append(f"\n\n### {rel}\n\n" + p.read_text(encoding="utf-8", errors="ignore").strip())
            section_names.append(rel)
            seen.add(rel)

        for sub in sorted(sec.iterdir()):
            if sub.is_dir():
                for p in sorted(sub.glob("*.md")):
                    if p.name.lower() in {"readme.md"}:
                        continue
                    rel = f"{section}/{sub.name}/{p.name}"
                    if rel in critical_tail_set:
                        continue
                    print(f"  📄 Adding: {rel}")
                    chunks.append(
                        f"\n\n### {rel}\n\n" + p.read_text(encoding="utf-8", errors="ignore").strip()
                    )
                    section_names.append(rel)
                    seen.add(rel)

    print("📌 Appending critical enforcement tail...")
    for rel in CRITICAL_TAIL:
        path = ROOT / "moodybot-system-prompt" / rel
        if not path.exists():
            print(f"  ⚠️  Missing critical module: {rel}")
            continue
        print(f"  📄 Tail: {rel}")
        chunks.append(f"\n\n### {rel}\n\n" + path.read_text(encoding="utf-8", errors="ignore").strip())
        section_names.append(rel)
        seen.add(rel)

    out = ROOT / "system_prompt.txt"
    body = "\n".join(chunks).strip() + "\n"
    out.write_text(body, encoding="utf-8")

    prompt_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    short_hash = prompt_hash[:16]
    total = len(section_names)

    critical_positions = {}
    for name in CRITICAL_NAMES:
        pos = None
        for i, sec_name in enumerate(section_names, 1):
            if name in sec_name:
                pos = i
        critical_positions[name] = pos

    meta = {
        "section_count": total,
        "char_count": len(body),
        "prompt_hash": short_hash,
        "prompt_hash_sha256": prompt_hash,
        "final_20_sections": section_names[-20:],
        "critical_module_positions": {
            k: (f"{v}/{total}" if v else "MISSING") for k, v in critical_positions.items()
        },
    }
    meta_path = ROOT / "prompt_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    print(f"✅ Wrote {out}")
    print(f"📊 Total sections processed: {total}")
    print(f"📏 Final size: {out.stat().st_size:,} bytes")
    print(f"🔐 Prompt hash: {short_hash}")
    print("CRITICAL MODULE ORDER")
    for name, pos in critical_positions.items():
        label = f"{pos}/{total}" if pos else "MISSING"
        print(f"  {name}: {label}")
    print("FINAL 20 SECTIONS")
    for name in section_names[-20:]:
        print(f"  - {name}")


if __name__ == "__main__":
    main()
