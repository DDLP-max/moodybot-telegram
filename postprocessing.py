# -*- coding: utf-8 -*-
"""
Post-processing pipeline for MoodyBot outputs.
Implements explicit stages with logging and proper-noun preservation.
"""

import os
import re
import json
import logging
from typing import Dict, Any, Set

# Initialize logger
logger = logging.getLogger("moodybot.postprocess")

def load_proper_noun_whitelist() -> Set[str]:
    """Load proper noun whitelist from JSON file."""
    try:
        with open("proper_nouns.json", "r", encoding="utf-8") as f:
            config = json.load(f)
            return set(config.get("PROPER_NOUN_WHITELIST", []))
    except Exception as e:
        logger.warning(f"Could not load proper noun whitelist: {e}")
        # Fallback to hardcoded list
        return {
            'Cialdini', 'Kahneman', 'Hahnemann', 'Tversky', 'Da Nang', 'Ala Wai', 
            'Donna Walden', 'MoodyBot', 'Ogilvy', 'Grok', 'OpenRouter', 'CapCut', 
            'Videoleap', 'Telegram', 'Da Tiki Queen'
        }

# Load proper noun whitelist
PROPER_NOUN_WHITELIST = load_proper_noun_whitelist()

def strip_markdownv2_escapes(text: str) -> str:
    """Remove any MarkdownV2 escapes since we use HTML mode."""
    # Remove backslashes before special characters that were escaped for MarkdownV2
    special_chars = r'\\([_*[\]()~`>#+=|{}.!-])'
    return re.sub(special_chars, r'\1', text)

def format_markdown(text: str) -> str:
    """Stage A: No escaping needed for HTML mode."""
    # Since we're using HTML parse mode, no Markdown escaping needed
    return text

def apply_output_filters(text: str) -> str:
    """
    Stage B: Apply output filters with proper-noun protection.
    NEVER runs spell/grammar correction on bot outputs by default.
    """
    # Check environment flag
    spellcheck_enabled = os.getenv('SPELLCHECK_BOT_OUTPUT', 'false').lower() == 'true'
    
    if not spellcheck_enabled:
        # Default: no lexical changes, only safe trimming if needed
        return text.strip()
    
    # If spellcheck is enabled, still protect whitelisted words
    return safe_filters(text, PROPER_NOUN_WHITELIST)

def safe_filters(text: str, whitelist: Set[str]) -> str:
    """
    Apply safe filters that don't modify whitelisted tokens.
    Only normalizes dangerous MarkdownV2 characters.
    """
    # Only normalize dangerous MarkdownV2 characters; do not change tokens
    return escape_markdown_v2(text)

def log_stages(stages: Dict[str, str]) -> None:
    """Log the different stages of post-processing for debugging."""
    if os.getenv('DEBUG', '').startswith('bot:postprocess'):
        logger.info("=== POST-PROCESSING STAGES ===")
        for stage_name, stage_content in stages.items():
            logger.info(f"{stage_name}: {stage_content[:100]}...")
        
        # Log diff if there are changes
        if stages.get('raw') != stages.get('stageB'):
            logger.info("=== CHANGES DETECTED ===")
            raw = stages.get('raw', '')
            final = stages.get('stageB', '')
            
            # Find first difference
            for i, (a, b) in enumerate(zip(raw, final)):
                if a != b:
                    logger.info(f"First change at position {i}: '{a}' -> '{b}'")
                    logger.info(f"Context: ...{raw[max(0, i-20):i+20]}...")
                    break

def soft_spellcheck_user_input(text: str) -> str:
    """
    Soft spellcheck for user input only.
    If confidence < 0.9, append a subtle hint but NEVER alter the token.
    """
    # This is a placeholder for future implementation
    # For now, just return the text as-is
    return text

def process_bot_output(raw_output: str) -> str:
    """
    Main post-processing pipeline for bot outputs.
    
    Args:
        raw_output: Raw output from the LLM
        
    Returns:
        Processed output ready for sending
    """
    # Stage A: Strip any MarkdownV2 escapes (since we use HTML mode)
    stage_a = strip_markdownv2_escapes(raw_output)
    
    # Stage B: Apply output filters (with proper-noun protection)
    stage_b = apply_output_filters(stage_a)
    
    # Stage C: Strip prefab phrases (if enabled)
    stage_c = stage_b
    if os.getenv('FILTER_PREFABS', 'true').lower() == 'true':
        stage_c = strip_prefab_phrases(stage_b)
    
    # Log all stages for debugging
    stages = {
        'raw': raw_output,
        'stageA': stage_a,
        'stageB': stage_b,
        'stageC': stage_c
    }
    log_stages(stages)
    
    return stage_c

def process_user_input(user_input: str) -> str:
    """
    Process user input with soft spellcheck.
    
    Args:
        user_input: Raw user input
        
    Returns:
        Processed user input with optional hints
    """
    return soft_spellcheck_user_input(user_input)

def is_whitelisted_token(token: str, whitelist: Set[str] = None) -> bool:
    """Check if a token is in the whitelist."""
    if whitelist is None:
        whitelist = PROPER_NOUN_WHITELIST
    
    # Check exact match and case-insensitive match
    return token in whitelist or token.lower() in {w.lower() for w in whitelist}

def preserve_whitelisted_tokens(text: str, whitelist: Set[str] = None) -> str:
    """
    Preserve whitelisted tokens during any text transformation.
    This is a safety function that can be called before any processing.
    """
    if whitelist is None:
        whitelist = PROPER_NOUN_WHITELIST
    
    # Find all whitelisted tokens in the text
    tokens_to_preserve = {}
    for token in whitelist:
        # Find all occurrences (case-insensitive)
        pattern = re.compile(re.escape(token), re.IGNORECASE)
        for match in pattern.finditer(text):
            start, end = match.span()
            placeholder = f"__PRESERVE_{len(tokens_to_preserve)}__"
            tokens_to_preserve[placeholder] = text[start:end]
    
    # Replace whitelisted tokens with placeholders
    protected_text = text
    for placeholder, original in tokens_to_preserve.items():
        protected_text = protected_text.replace(original, placeholder)
    
    return protected_text, tokens_to_preserve

def restore_whitelisted_tokens(text: str, tokens_to_preserve: Dict[str, str]) -> str:
    """Restore whitelisted tokens after processing."""
    restored_text = text
    for placeholder, original in tokens_to_preserve.items():
        restored_text = restored_text.replace(placeholder, original)
    return restored_text

def strip_prefab_phrases(text: str) -> str:
    """
    Strip unwanted prefab phrases from bot outputs.
    Removes common filler phrases like "ah, ..." and "oh, reckless mess".
    """
    original_text = text
    cleaned_text = text
    
    # Define prefab phrases to remove (case-insensitive)
    # Order matters - more specific patterns first
    prefab_patterns = [
        # "ah, reckless mess" and similar combinations
        r'^ah,\s*reckless\s+mess,?\s*',
        r'^ah\s+reckless\s+mess,?\s*',
        
        # "oh, reckless mess" and similar combinations
        r'^oh,\s*reckless\s+mess,?\s*',
        r'^oh\s+reckless\s+mess,?\s*',
        
        # "you beautiful mess" and similar validation phrases (when used as filler)
        r'^you\s+beautiful\s+mess,?\s*',
        r'^you\s+lovable\s+disaster,?\s*',
        r'^you\s+storm\s+in\s+eyeliner,?\s*',
        r'^you\s+slow\s+burn\s+in\s+a\s+matchstick\s+world,?\s*',
        r'^you\s+chaos\s+with\s+a\s+conscience,?\s*',
        
        # Generic leading patterns (less specific, applied last)
        r'^ah,\s*',
        r'^ah\s+',
        r'^oh,\s*',
        r'^oh\s+',
    ]
    
    # Apply each pattern
    for pattern in prefab_patterns:
        # Check if pattern matches
        if re.search(pattern, cleaned_text, re.IGNORECASE):
            # Log the removal for debugging
            if os.getenv('DEBUG', '').startswith('bot:postprocess'):
                match = re.search(pattern, cleaned_text, re.IGNORECASE)
                if match:
                    removed_phrase = match.group(0)
                    logger.info(f"STRIPPED PREFAB: '{removed_phrase}' from: {cleaned_text[:50]}...")
            
            # Remove the pattern
            cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE)
    
    # Clean up any extra whitespace left behind
    cleaned_text = re.sub(r'^\s+', '', cleaned_text)  # Remove leading whitespace
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text)  # Normalize internal whitespace
    
    # Log if any changes were made
    if cleaned_text != original_text and os.getenv('DEBUG', '').startswith('bot:postprocess'):
        logger.info(f"PREFAB STRIPPING: '{original_text[:50]}...' -> '{cleaned_text[:50]}...'")
    
    return cleaned_text
