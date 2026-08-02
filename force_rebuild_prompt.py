#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Force Rebuild System Prompt
Use this script when you want to manually rebuild the system prompt
regardless of whether files have changed.
"""

import subprocess
import os
import time

def force_rebuild_system_prompt():
    """Force rebuild the system prompt"""
    print("🔄 Force rebuilding system prompt...")
    
    # Check if build script exists
    if not os.path.exists("build_system_prompt.py"):
        print("❌ Error: build_system_prompt.py not found!")
        return False
    
    # Run the build script
    try:
        result = subprocess.run(
            ["python", "build_system_prompt.py"], 
            capture_output=True, 
            text=True, 
            check=True
        )
        print("✅ System prompt rebuilt successfully!")
        print(f"Output: {result.stdout}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error rebuilding system prompt: {e}")
        print(f"Error output: {e.stderr}")
        return False
    except FileNotFoundError:
        print("❌ Error: Python not found in PATH")
        return False

if __name__ == "__main__":
    print("🔧 Force Rebuild System Prompt Tool")
    print("=" * 40)
    
    # Check current system prompt
    if os.path.exists("system_prompt.txt"):
        mtime = os.path.getmtime("system_prompt.txt")
        size = os.path.getsize("system_prompt.txt")
        print(f"Current system prompt: {size:,} bytes")
        print(f"Last modified: {time.ctime(mtime)}")
    else:
        print("No existing system prompt found.")
    
    print()
    
    # Confirm rebuild
    response = input("Are you sure you want to force rebuild? (y/N): ").strip().lower()
    
    if response in ['y', 'yes']:
        success = force_rebuild_system_prompt()
        if success:
            print("\n🎉 Rebuild complete! You can now restart the bots.")
        else:
            print("\n💥 Rebuild failed. Check the error messages above.")
    else:
        print("❌ Rebuild cancelled.")
