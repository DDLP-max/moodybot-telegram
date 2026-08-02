#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to check access to moodybot-system-prompt directory
"""

import pathlib
import os

print("🔍 Testing access to moodybot-system-prompt directory...")

# Check current directory
current_dir = pathlib.Path.cwd()
print(f"Current directory: {current_dir}")

# Check if moodybot-system-prompt exists
prompt_dir = current_dir / "moodybot-system-prompt"
print(f"Prompt directory path: {prompt_dir}")
print(f"Prompt directory exists: {prompt_dir.exists()}")

if prompt_dir.exists():
    print(f"Prompt directory is directory: {prompt_dir.is_dir()}")
    
    # List contents
    print("\n📁 Contents of moodybot-system-prompt:")
    for item in sorted(prompt_dir.iterdir()):
        if item.is_dir():
            print(f"  📁 {item.name}/")
        else:
            print(f"  📄 {item.name}")
    
    # Check specific sections
    print("\n🔍 Checking specific sections:")
    sections = ["8_response-engine", "1_emotional-architecture", "2_personality-engine"]
    
    for section in sections:
        section_path = prompt_dir / section
        if section_path.exists():
            print(f"  ✅ {section} exists")
            # Count .md files
            md_files = list(section_path.glob("*.md"))
            print(f"     Contains {len(md_files)} .md files")
            
            # Check for dynamic persona files
            if section == "8_response-engine":
                dynamic_files = [f for f in md_files if "dynamic" in f.name.lower()]
                print(f"     Dynamic persona files: {[f.name for f in dynamic_files]}")
        else:
            print(f"  ❌ {section} not found")
else:
    print("❌ moodybot-system-prompt directory not found!")
    
    # List current directory contents
    print("\n📁 Current directory contents:")
    for item in sorted(current_dir.iterdir()):
        if item.is_dir():
            print(f"  📁 {item.name}/")
        else:
            print(f"  📄 {item.name}")


