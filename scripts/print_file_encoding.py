#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File Encoding Debugging Tool

Given a file path, prints the likely encoding and the first few bytes (hex) for debugging.
"""

import sys
import codecs
import os

def sniff_encoding(path):
    """Sniff the encoding of a file and return details."""
    if not os.path.exists(path):
        print(f"Error: File '{path}' does not exist")
        return
    
    try:
        with open(path, 'rb') as f:
            b = f.read()
    except Exception as e:
        print(f"Error reading file '{path}': {e}")
        return
    
    head = b[:16]  # First 16 bytes
    enc = 'unknown'
    
    # Check for BOMs
    if b.startswith(codecs.BOM_UTF8):
        enc = 'utf-8-sig (UTF-8 with BOM)'
    elif b.startswith(codecs.BOM_UTF16_LE):
        enc = 'utf-16-le (UTF-16 Little Endian with BOM)'
    elif b.startswith(codecs.BOM_UTF16_BE):
        enc = 'utf-16-be (UTF-16 Big Endian with BOM)'
    else:
        # Try to decode with different encodings
        for encoding in ('utf-8', 'utf-16', 'utf-16-le', 'utf-16-be', 'cp1252', 'latin-1'):
            try:
                b.decode(encoding)
                enc = encoding
                break
            except UnicodeDecodeError:
                continue
    
    print(f"File: {path}")
    print(f"Size: {len(b)} bytes")
    print(f"Detected encoding: {enc}")
    print(f"First 16 bytes (hex): {head.hex(' ')}")
    print(f"First 16 bytes (repr): {repr(head)}")
    
    # Try to show first few characters if possible
    try:
        text = b.decode(enc.split()[0] if ' ' in enc else enc)
        preview = text[:50].replace('\n', '\\n').replace('\r', '\\r')
        print(f"Text preview: {preview}...")
    except:
        print("Text preview: (cannot decode)")

def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python print_file_encoding.py <file1> [file2] ...")
        print("Example: python print_file_encoding.py replit/build_system_prompt.py")
        sys.exit(1)
    
    for path in sys.argv[1:]:
        sniff_encoding(path)
        if len(sys.argv) > 2:  # Multiple files
            print("-" * 50)

if __name__ == '__main__':
    main()

