#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UTF-8 Encoding Enforcement Script

Scans the project for text files and ensures they are properly encoded as UTF-8 (no BOM).
Detects and converts various encodings to UTF-8, and adds encoding headers to Python files.
"""

import sys
import os
import argparse
import codecs
import re
from pathlib import Path

# File extensions to process
TEXT_EXTS = {
    '.py', '.md', '.json', '.yml', '.yaml', '.txt', '.ini', '.toml', 
    '.js', '.ts', '.tsx', '.css', '.html', '.mdx', '.sh', '.cfg'
}

# Directories to skip
SKIP_DIRS = {
    '.git', '.venv', 'venv', 'node_modules', 'dist', 'build', 
    '__pycache__', '.mypy_cache', '.pytest_cache'
}

# File patterns to skip
SKIP_GLOBS = (
    '.png', '.jpg', '.jpeg', '.gif', '.webp', '.pdf', '.ico', 
    '.zip', '.tar', '.gz', '.dll', '.exe'
)

# Python encoding header
ENC_HEADER = "# -*- coding: utf-8 -*-\n"
SHEBANG_RE = re.compile(br'^#!.*\n')

def is_text_path(path):
    """Check if a file path should be processed as a text file."""
    path_str = str(path)
    ext = os.path.splitext(path_str)[1].lower()
    
    # Check if extension is in our list
    if ext in TEXT_EXTS:
        return True
    
    # Check if it matches any skip patterns
    for pattern in SKIP_GLOBS:
        if path_str.lower().endswith(pattern):
            return False
    
    return False

def read_bytes(path):
    """Read file as raw bytes."""
    with open(path, 'rb') as f:
        return f.read()

def detect_decode(b):
    """
    Detect encoding and decode bytes to text.
    Returns (decoded_text, detected_encoding)
    """
    # Check for BOMs first
    if b.startswith(codecs.BOM_UTF8):
        return b[len(codecs.BOM_UTF8):].decode('utf-8'), 'utf-8-sig'
    if b.startswith(codecs.BOM_UTF16_LE):
        return b[len(codecs.BOM_UTF16_LE):].decode('utf-16-le'), 'utf-16-le'
    if b.startswith(codecs.BOM_UTF16_BE):
        return b[len(codecs.BOM_UTF16_BE):].decode('utf-16-be'), 'utf-16-be'
    
    # Try UTF-8 strict first
    try:
        return b.decode('utf-8'), 'utf-8'
    except UnicodeDecodeError:
        pass
    
    # Try other common encodings
    for enc in ('utf-8-sig', 'utf-16', 'utf-16-le', 'utf-16-be', 'cp1252', 'latin-1'):
        try:
            return b.decode(enc), enc
        except UnicodeDecodeError:
            continue
    
    # Last resort: replace errors to avoid crash
    return b.decode('utf-8', errors='replace'), 'utf-8?replace'

def ensure_py_encoding_header(text):
    """Ensure Python file has UTF-8 encoding header."""
    lines = text.splitlines(keepends=True)
    if not lines:
        return ENC_HEADER
    
    # Check if shebang is present
    has_shebang = lines[0].startswith('#!')
    
    # Check first two lines for existing UTF-8 header
    header_present = False
    for i in range(min(2, len(lines))):
        if 'coding:' in lines[i].lower() and 'utf-8' in lines[i].lower():
            header_present = True
            break
    
    if header_present:
        return text
    
    # Add encoding header
    if has_shebang:
        return lines[0] + ENC_HEADER + ''.join(lines[1:])
    else:
        return ENC_HEADER + ''.join(lines)

def process_file(path, fix=False, verbose=False):
    """Process a single file for encoding issues."""
    try:
        b = read_bytes(path)
        orig_b = b
        text, enc = detect_decode(b)
        changed = False
        reason = []
        
        # For Python files: ensure encoding header
        if path.lower().endswith('.py'):
            new_text = ensure_py_encoding_header(text)
            if new_text != text:
                text = new_text
                changed = True
                reason.append('add-encoding-header')
        
        # If decoded via anything other than plain UTF-8, rewrite as UTF-8
        if enc != 'utf-8':
            changed = True
            reason.append(f'{enc}->utf-8')
        
        # Write changes if requested
        if changed and fix:
            with open(path, 'w', encoding='utf-8', newline='') as f:
                f.write(text)
        
        # Log results
        if verbose or changed:
            status = '[FIX]' if (changed and fix) else '[CHK]'
            reasons = ', '.join(reason) if reason else 'ok'
            print(f"{status} {path} :: {reasons}")
        
        return changed, reason
        
    except Exception as e:
        print(f"[ERROR] {path} :: {e}")
        return False, ['error']

def walk(root, fix=False, verbose=False):
    """Walk directory tree and process all text files."""
    total = scanned = fixed = 0
    changes = []
    
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skip directories
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        
        for name in filenames:
            path = os.path.join(dirpath, name)
            if not is_text_path(path):
                continue
            
            scanned += 1
            changed, reasons = process_file(path, fix=fix, verbose=verbose)
            
            if changed:
                fixed += 1
                changes.append((path, reasons))
    
    # Print summary
    action = 'Converted' if fix else 'Needs fix'
    print(f"\nScanned: {scanned} text files | {action}: {fixed}")
    
    if changes and verbose:
        print("\nChanges made:")
        for path, reasons in changes:
            print(f"  {path}: {', '.join(reasons)}")
    
    return changes

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Ensure all text files are properly encoded as UTF-8'
    )
    parser.add_argument(
        '--fix', 
        action='store_true', 
        help='Write changes to disk (default: dry run)'
    )
    parser.add_argument(
        '--verbose', 
        action='store_true',
        help='Print detailed output for each file'
    )
    parser.add_argument(
        '--root', 
        default='.', 
        help='Project root directory (default: current directory)'
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.root):
        print(f"Error: Root directory '{args.root}' does not exist")
        sys.exit(1)
    
    print(f"Scanning for encoding issues in: {os.path.abspath(args.root)}")
    if not args.fix:
        print("(Dry run mode - use --fix to apply changes)")
    
    changes = walk(args.root, fix=args.fix, verbose=args.verbose)
    
    if changes and not args.fix:
        print(f"\nFound {len(changes)} files that need conversion.")
        print("Run with --fix to apply changes.")
        sys.exit(1)
    elif not changes:
        print("All files are properly encoded!")

if __name__ == '__main__':
    main()

