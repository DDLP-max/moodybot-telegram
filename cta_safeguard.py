#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Safeguard to detect any remaining file-based CTA/footer injection.
Run this during development to ensure no .txt files are read for CTAs.
"""

import os
import ast
import re
from typing import List, Tuple

def find_file_reads_for_ctas() -> List[Tuple[str, int, str]]:
    """
    Scan Python files for any code that reads .txt/.md/.yaml files for CTAs.
    Returns list of (filename, line_number, code_line) tuples.
    """
    issues = []
    
    # Keywords that suggest CTA/footer loading
    cta_keywords = ['cta', 'footer', 'signature', 'outro', 'tagline', 'ps']
    file_extensions = ['.txt', '.md', '.yaml', '.yml']
    
    for root, dirs, files in os.walk('.'):
        # Skip certain directories
        dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', '.venv', 'venv', 'node_modules']]
        
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        lines = content.split('\n')
                        
                        for i, line in enumerate(lines, 1):
                            # Check for file operations with CTA-related keywords
                            if any(keyword in line.lower() for keyword in cta_keywords):
                                if any(ext in line for ext in file_extensions):
                                    if 'open(' in line or 'read(' in line or 'load(' in line:
                                        issues.append((filepath, i, line.strip()))
                                        
                except Exception as e:
                    print(f"Error reading {filepath}: {e}")
    
    return issues

def check_for_markdownv2_usage() -> List[Tuple[str, int, str]]:
    """
    Check for any remaining MarkdownV2 usage.
    """
    issues = []
    
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', '.venv', 'venv', 'node_modules']]
        
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        lines = content.split('\n')
                        
                        for i, line in enumerate(lines, 1):
                            if 'MarkdownV2' in line or 'parse_mode.*Markdown' in line:
                                issues.append((filepath, i, line.strip()))
                                        
                except Exception as e:
                    print(f"Error reading {filepath}: {e}")
    
    return issues

def main():
    """Run all checks and report issues."""
    print("🔍 Checking for file-based CTA/footer injection...")
    
    cta_issues = find_file_reads_for_ctas()
    markdown_issues = check_for_markdownv2_usage()
    
    if cta_issues:
        print("❌ Found file-based CTA loading:")
        for filepath, line_num, code in cta_issues:
            print(f"  {filepath}:{line_num} - {code}")
    else:
        print("✅ No file-based CTA loading found")
    
    if markdown_issues:
        print("❌ Found MarkdownV2 usage:")
        for filepath, line_num, code in markdown_issues:
            print(f"  {filepath}:{line_num} - {code}")
    else:
        print("✅ No MarkdownV2 usage found")
    
    if not cta_issues and not markdown_issues:
        print("🎉 All checks passed! No file-based CTAs or MarkdownV2 usage detected.")
        return True
    else:
        print("⚠️  Issues found. Please fix before deploying.")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

