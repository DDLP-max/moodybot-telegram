#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to set the OpenRouter API key in the database configuration.
Run this script to configure your API keys.
"""

import os
import sys
from dotenv import load_dotenv

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import db, BotConfig
from config import set_config_value

def main():
    print("🔧 MoodyBot API Key Configuration")
    print("=" * 40)
    
    # Load environment variables if .env exists
    load_dotenv()
    
    # Get current values
    current_openrouter_key = os.getenv("OPENROUTER_API_KEY")
    current_telegram_key = os.getenv("TELEGRAM_BOT_TOKEN")
    
    print(f"Current OpenRouter API Key: {'*' * 20 if current_openrouter_key else 'NOT SET'}")
    print(f"Current Telegram Bot Token: {'*' * 20 if current_telegram_key else 'NOT SET'}")
    print()
    
    # Get new OpenRouter API key
    print("Enter your OpenRouter API key (or press Enter to skip):")
    new_openrouter_key = input("OpenRouter API Key: ").strip()
    
    if new_openrouter_key:
        # Set in database
        if set_config_value("OPENROUTER_API_KEY", new_openrouter_key):
            print("✅ OpenRouter API key saved to database!")
        else:
            print("❌ Failed to save OpenRouter API key to database")
    
    # Get new Telegram Bot Token
    print("\nEnter your Telegram Bot Token (or press Enter to skip):")
    new_telegram_key = input("Telegram Bot Token: ").strip()
    
    if new_telegram_key:
        # Set in database
        if set_config_value("TELEGRAM_BOT_TOKEN", new_telegram_key):
            print("✅ Telegram Bot Token saved to database!")
        else:
            print("❌ Failed to save Telegram Bot Token to database")
    
    print("\n🎉 Configuration complete!")
    print("You can now run the bot with: python moodybot.py")

if __name__ == "__main__":
    main() 