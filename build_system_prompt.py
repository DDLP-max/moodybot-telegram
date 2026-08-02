#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced MoodyBot System Prompt Builder
Automatically compiles all markdown files from the modular system prompt directory
Includes recursive scanning for subdirectories (like personas)
"""

import sys

# Windows consoles often default to CP1252; keep emoji logging readable.
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import pathlib
import re

# Set the root to the current directory (replit folder)
ROOT = pathlib.Path.cwd()
ORDER = [
    "1_emotional-architecture",
    "2_personality-engine", 
    "3_formatting-structure",
    "4_safety-protocols",
    "5_engagement-conversion",
    "6_design-process",
    "7_emotional-modulation",
    "8_response-engine",
    "9_testing-quality"
]

chunks = []

for section in ORDER:
    sec = ROOT / "moodybot-system-prompt" / section
    if not sec.exists():
        print(f"⚠️  Section {section} not found, skipping...")
        continue
    
    print(f"📁 Processing section: {section}")
    
    # pull top-level .md files in alpha order
    for p in sorted(sec.glob("*.md")):
        if p.name.lower() in {"readme.md"}:
            continue
        print(f"  📄 Adding: {section}/{p.name}")
        chunks.append(f"\n\n### {section}/{p.name}\n\n" + p.read_text(encoding="utf-8", errors="ignore").strip())
    
    # pull nested folders (e.g., personas)
    for sub in sorted(sec.iterdir()):
        if sub.is_dir():
            for p in sorted(sub.glob("*.md")):
                if p.name.lower() in {"readme.md"}:
                    continue
                print(f"  📄 Adding: {section}/{sub.name}/{p.name}")
                chunks.append(f"\n\n### {section}/{sub.name}/{p.name}\n\n" + p.read_text(encoding="utf-8", errors="ignore").strip())

# Write to the replit folder
out = ROOT / "system_prompt.txt"
out.write_text("\n".join(chunks).strip() + "\n", encoding="utf-8")
print(f"✅ Wrote {out}")
print(f"📊 Total sections processed: {len(chunks)}")
print(f"📏 Final size: {out.stat().st_size:,} bytes")
