#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quick setup script for MoodyBot API keys.
This creates a simple config file that the bot can read.
"""

import os
import json

def main():
    print("🔧 MoodyBot Quick Setup")
    print("=" * 30)
    
    # Get API keys from user
    print("Enter your OpenRouter API key:")
    openrouter_key = input("OpenRouter API Key: ").strip()
    
    print("\nEnter your Telegram Bot Token:")
    telegram_key = input("Telegram Bot Token: ").strip()
    
    if not openrouter_key or not telegram_key:
        print("❌ Both API keys are required!")
        return
    
    # Create config dictionary
    config = {
        "OPENROUTER_API_KEY": openrouter_key,
        "TELEGRAM_BOT_TOKEN": telegram_key
    }
    
    # Save to config file
    try:
        with open("api_config.json", "w") as f:
            json.dump(config, f, indent=2)
        print("✅ API keys saved to api_config.json")
    except Exception as e:
        print(f"❌ Failed to save config: {e}")
        return
    
    # Also create a simple .env file content for reference
    env_content = f"""# MoodyBot Configuration
TELEGRAM_BOT_TOKEN={telegram_key}
OPENROUTER_API_KEY={openrouter_key}
"""
    
    try:
        with open("env_template.txt", "w") as f:
            f.write(env_content)
        print("✅ Environment template saved to env_template.txt")
        print("   Copy the contents to a .env file if needed")
    except Exception as e:
        print(f"⚠️ Could not create env template: {e}")
    
    print("\n🎉 Setup complete!")
    print("You can now run the bot with: python moodybot.py")

if __name__ == "__main__":
    main() 