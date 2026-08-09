#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Message sending utilities for MoodyBot.
Handles HTML formatting, CTA appending, and mode detection.
"""

import os
import re
import json
import logging
from typing import Optional, Dict, Any
from telegram import Update

logger = logging.getLogger("moodybot.message_utils")

# Environment configuration
APPEND_CTA = os.getenv('APPEND_CTA', 'true').lower() == 'true'

def load_ctas_from_env() -> Dict[str, str]:
    """Load CTAs from environment variable JSON config."""
    try:
        ctas_json = os.getenv('CTAS_JSON', '{}')
        ctas = json.loads(ctas_json)
        return ctas
    except Exception as e:
        logger.warning(f"Could not load CTAs from env: {e}")
        # Fallback to default CTAs
        return {
            "flirt": "If it read your soul, put it on speaker 🔁",
            "social": "Pass the vibe forward ➡️",
            "dev": "Code it, ship it, break it 🔧",
            "copywriter": "Words that sell, stories that stick ✍️"
        }

# Load CTAs from environment
CTAS_CONFIG = load_ctas_from_env()

def escape_html(text: str) -> str:
    """
    Escape HTML special characters for Telegram HTML parse mode.
    Only escapes the characters that need escaping in HTML.
    """
    html_escapes = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
    }
    
    for char, escaped in html_escapes.items():
        text = text.replace(char, escaped)
    
    return text

def format_html_message(text: str) -> str:
    """
    Format text for HTML parse mode.
    Converts basic Markdown-style formatting to HTML.
    """
    # Escape HTML special characters first
    text = escape_html(text)
    
    # Convert basic formatting
    # Bold: **text** -> <b>text</b>
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    
    # Italic: *text* -> <i>text</i>
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    
    # Underline: __text__ -> <u>text</u>
    text = re.sub(r'__(.*?)__', r'<u>\1</u>', text)
    
    # Strikethrough: ~~text~~ -> <s>text</s>
    text = re.sub(r'~~(.*?)~~', r'<s>\1</s>', text)
    
    # Code: `text` -> <code>text</code>
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    
    # Pre-formatted: ```text``` -> <pre>text</pre>
    text = re.sub(r'```(.*?)```', r'<pre>\1</pre>', text, flags=re.DOTALL)
    
    # Links: [text](url) -> <a href="url">text</a>
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    
    return text

def resolve_mode(update: Update) -> str:
    """
    Detect the mode from user commands or message content.
    Returns: 'flirt', 'social', 'dev', 'copywriter', 'neutral', etc.
    """
    if not update or not update.message:
        return 'neutral'
    
    user_input = update.message.text.lower()
    
    # Check for explicit mode commands
    mode_commands = {
        '/flirt': 'flirt',
        '/social': 'social', 
        '/dev': 'dev',
        '/copywriter': 'copywriter',
        '/neutral': 'neutral',
        '/clinical': 'clinical',
        '/savage': 'savage',
        '/velvet': 'velvet',
        '/noir': 'noir',
    }
    
    for command, mode in mode_commands.items():
        if command in user_input:
            return mode
    
    # Check for mode indicators in message content
    if any(word in user_input for word in ['flirt', 'seductive', 'charming', 'romantic']):
        return 'flirt'
    elif any(word in user_input for word in ['social', 'share', 'post', 'timeline']):
        return 'social'
    elif any(word in user_input for word in ['dev', 'developer', 'code', 'technical']):
        return 'dev'
    elif any(word in user_input for word in ['copy', 'copywriter', 'marketing', 'ad']):
        return 'copywriter'
    
    # Default to neutral
    return 'neutral'

def strip_known_ctas(text: str) -> str:
    """
    Remove any previously deployed CTA lines to prevent legacy leftovers.
    """
    # Common CTA patterns to remove
    cta_patterns = [
        r'\n\nIf it read your soul, put it on speaker 🔁.*$',
        r'\n\nIf it slapped, share the sting.*$',
        r'\n\nTruth hurts, but damn it hits\. Share it 🔁.*$',
        r'\n\nYou feel that\? Clip it, post it, haunt someone 🔁.*$',
        r'\n\nSomeone else needs to hear this\. Be the villain\. 🔁.*$',
        r'\n\nNo one\'s coming to save them\. Share it anyway 🔁.*$',
        r'\n\nIf it ruined your day, ruin someone else\'s 🔁.*$',
        r'\n\nThey won\'t get the hint, so send the hammer 🔁.*$',
        r'\n\nTruth is heavier when it\'s forwarded\. Try it 🔁.*$',
        r'\n\nEcho it\. Quote it\. Make them flinch 🔁.*$',
        r'\n\nIf it opened a wound, let it bleed on the timeline 🔁.*$',
        r'\n\nTurn this message into a mirror\. Break someone open 🔁.*$',
        r'\n\nValidation or violence — MoodyBot delivers 🔁.*$',
        r'\n\nPost it like a warning\. Watch who flinches 🔁.*$',
        r'\n\nDon\'t keep the damage to yourself\. Spread it 🔁.*$',
        r'\n\nThis is a literary weapon\. Reload it 🔁.*$',
        r'\n\nTag someone who needs the clarity, not the comfort 🔁.*$',
        r'\n\nToo real to ignore\. Too late to deny\. 🔁.*$',
        r'\n\nMake your enemies feel it\. MoodyBot said so 🔁.*$',
        r'\n\nIf it healed something, or hurt something — share it 🔁.*$',
        r'\n\nLet the ghosts know you\'re not haunted alone 🔁.*$',
        r'\n\nHit that 🔁 like you just burned a bridge on purpose.*$',
        r'\n\nMoodyBot doesn\'t whisper\. Neither should you 🔁.*$',
        r'\n\nYou\'re not alone\. Just early\. Share it 🔁.*$',
        r'\n\nIt\'s not like sharing costs you anything\. 🔁.*$',
        r'\n\nYou get to look cooler\. They get to hurt smarter\. 🔁.*$',
        r'\n\nGood things rot when you hoard them\. Share the damage 🔁.*$',
        r'\n\nDon\'t be selfish\. Someone out there needs this slap worse than you 🔁.*$',
        r'\n\nKeeping MoodyBot to yourself\? Cute\. Selfish\. 🔁.*$',
        r'\n\nYou survived the hit\. Be generous\. Send it 🔁.*$',
        r'\n\nPost it\. Clip it\. Pretend you wrote it\. I won\'t snitch 🔁.*$',
        r'\n\nYou\'re cooler for echoing MoodyBot than for scrolling past 🔁.*$',
        r'\n\nSharing this is cheaper than therapy\. And looks better 🔁.*$',
        r'\n\nImpress your smarter friends\. Disturb the fake ones\. Share it 🔁.*$',
        r'\n\nIf it scarred you, don\'t heal quietly\. Scar louder 🔁.*$',
        r'\n\nThe real ones will save it\. The cowards will scroll 🔁.*$',
        r'\n\nShare it like you\'re sending a warning shot 🔁.*$',
        r'\n\nSomeone\'s gonna flinch when they read it\. Let it be your fault 🔁.*$',
        r'\n\nPress 🔁 if you\'ve got better taste than your timeline.*$',
        r'\n\nMoodyBot\'s not whispering\. Neither should you 🔁.*$',
        r'\n\nSave it\. Share it\. Sin with it 🔁.*$',
        # Generic patterns
        r'\n\n.*🔁.*$',
        r'\n\n.*share.*it.*🔁.*$',
        r'\n\n.*post.*it.*🔁.*$',
        r'\n\n.*clip.*it.*🔁.*$',
    ]
    
    cleaned_text = text
    for pattern in cta_patterns:
        cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE | re.MULTILINE)
    
    return cleaned_text.strip()

def cta_for_mode(mode: str) -> str:
    """Get CTA for specific mode from environment config."""
    return CTAS_CONFIG.get(mode, "")

def maybe_append_cta(text: str, mode: str) -> str:
    """
    Conditionally append CTA based on mode and environment flag.
    Only appends CTA for modes that have CTAs configured when APPEND_CTA is enabled.
    """
    if not APPEND_CTA:
        return text
    
    # Get CTA for this mode
    cta = cta_for_mode(mode)
    if not cta:
        return text
    
    # Don't append if already has CTA
    if '🔁' in text or 'share' in text.lower() or 'post' in text.lower():
        return text
    
    return f"{text}\n\n{cta}"

async def send_message(
    update: Update,
    text: str,
    mode: Optional[str] = None,
    allow_cta: bool = False,
) -> None:
    """
    Send a message with proper HTML formatting and conditional CTA.
    
    Args:
        update: Telegram Update object
        text: Message text to send
        mode: Optional mode override (if None, will auto-detect)
        allow_cta: Engagement share CTAs are OFF by default so they cannot
            overwrite recognition callbacks / silence / action closers.
    """
    if not update or not update.message:
        logger.error("Invalid update or message")
        return
    
    # Auto-detect mode if not provided
    if mode is None:
        mode = resolve_mode(update)
    
    # Clean up any legacy CTAs first
    cleaned_text = strip_known_ctas(text)
    
    # Apply CTA only when explicitly allowed (engagement is last)
    formatted_text = maybe_append_cta(cleaned_text, mode) if allow_cta else cleaned_text
    
    # Format for HTML parse mode
    html_text = format_html_message(formatted_text)
    try:
        from gold_shape import paragraph_count as _paragraph_count

        logger.info(
            "PARA_TRACE_TELEGRAM mode=%s telegram_payload_paragraph_count=%s",
            mode,
            _paragraph_count(formatted_text),
        )
    except Exception:
        pass

    try:
        # Send with HTML parse mode
        await update.message.reply_text(html_text, parse_mode='HTML')
        logger.info(f"Message sent successfully in {mode} mode")
    except Exception as e:
        logger.error(f"Failed to send HTML message: {e}")
        try:
            # Fallback to plain text
            await update.message.reply_text(formatted_text)
            logger.info("Fallback to plain text successful")
        except Exception as e2:
            logger.error(f"Failed to send fallback message: {e2}")

async def send_simple_message(update: Update, text: str) -> None:
    """
    Send a simple message without formatting or CTA.
    Useful for error messages and system responses.
    """
    if not update or not update.message:
        logger.error("Invalid update or message")
        return
    
    try:
        await update.message.reply_text(text)
    except Exception as e:
        logger.error(f"Failed to send simple message: {e}")

# Backward compatibility functions
async def reply_text_html(update: Update, text: str, mode: Optional[str] = None) -> None:
    """Async wrapper for send_message."""
    send_message(update, text, mode)

def strip_cta_from_text(text: str) -> str:
    """
    Remove CTA lines from text.
    Useful for cleaning up text before processing.
    """
    # Remove lines that look like CTAs (contain 🔁 or common CTA phrases)
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line_stripped = line.strip()
        # Skip lines that look like CTAs (more specific patterns)
        if (line_stripped.endswith('🔁') or 
            line_stripped.startswith('Share this message') or
            line_stripped.startswith('Post it') or
            line_stripped.startswith('Clip it') or
            line_stripped.startswith('Forward') and 'it' in line_stripped.lower()):
            continue
        cleaned_lines.append(line)  # Keep original line (with whitespace)
    
    return '\n'.join(cleaned_lines).strip()
