# Telegram Bot Message Refactoring

This document describes the refactoring of the Telegram bot message sending code to fix two key issues:

1. **Markdown backslashes**: Messages showed unwanted backslashes (e.g. "Nah\." instead of "Nah.")
2. **Stray CTA/footer**: The line "If it read your soul, put it on speaker 🔁" was appended to every reply

## Solution Overview

### 1. HTML Parse Mode
- Switched from `parse_mode='Markdown'` to `parse_mode='HTML'`
- Implemented proper HTML formatting that only escapes necessary characters
- No more unwanted backslashes in messages

### 2. Conditional CTA Appending
- Added environment flag `APPEND_CTA=true/false` (default: true)
- CTAs only appended for 'flirt' and 'social' modes
- Other modes (dev, copywriter, neutral) get clean messages without CTAs

## New Architecture

### Core Files

**`message_utils.py`** - Main message utilities module:
- `send_message()` - Main message sending function with HTML formatting
- `format_html_message()` - Converts Markdown-style to HTML
- `resolve_mode()` - Detects mode from user commands/content
- `maybe_append_cta()` - Conditionally appends CTA based on mode
- `strip_cta_from_text()` - Removes CTAs from text
- `escape_html()` - Escapes HTML special characters

### Key Functions

#### `send_message(update, text, mode=None)`
```python
# Main message sending function
send_message(update, "**Bold text** and *italic*", 'flirt')
# Sends: <b>Bold text</b> and <i>italic</i> with CTA appended
```

#### `resolve_mode(update)`
```python
# Auto-detects mode from user input
modes = {
    '/flirt': 'flirt',
    '/social': 'social', 
    '/dev': 'dev',
    '/copywriter': 'copywriter',
    '/neutral': 'neutral'
}
```

#### `maybe_append_cta(text, mode)`
```python
# Only appends CTA for flirt/social modes when APPEND_CTA=true
maybe_append_cta("Hello world", 'flirt')  # Adds CTA
maybe_append_cta("Hello world", 'dev')    # No CTA
```

## Usage Examples

### Before (Markdown with backslashes)
```python
await update.message.reply_text(
    "**Bold text** and *italic* with backslashes\\.", 
    parse_mode='Markdown'
)
# Result: "**Bold text** and *italic* with backslashes\."
```

### After (HTML, clean formatting)
```python
send_message(update, "**Bold text** and *italic* with clean formatting.", 'neutral')
# Result: "<b>Bold text</b> and <i>italic</i> with clean formatting."
```

### CTA Behavior

#### Flirt/Social Mode (CTA added)
```python
send_message(update, "You're amazing!", 'flirt')
# Result: "You're amazing! 🥃\n\nIf it read your soul, put it on speaker 🔁"
```

#### Dev/Copywriter Mode (No CTA)
```python
send_message(update, "Here's the code solution.", 'dev')
# Result: "Here's the code solution. 🥃"
```

## Environment Configuration

### Production Settings
```bash
APPEND_CTA=true    # Enable CTA for flirt/social modes
```

### Development Settings
```bash
APPEND_CTA=false   # Disable all CTAs for testing
```

## Mode Detection

The system automatically detects modes from:

1. **Explicit commands**: `/flirt`, `/social`, `/dev`, `/copywriter`
2. **Content keywords**: 
   - "flirt", "seductive" → flirt mode
   - "social", "share", "post" → social mode
   - "dev", "code", "technical" → dev mode
   - "copy", "marketing", "ad" → copywriter mode
3. **Default**: neutral mode

## HTML Formatting

Converts Markdown-style formatting to HTML:

| Markdown | HTML | Result |
|----------|------|--------|
| `**bold**` | `<b>bold</b>` | **bold** |
| `*italic*` | `<i>italic</i>` | *italic* |
| `__underline__` | `<u>underline</u>` | <u>underline</u> |
| `~~strike~~` | `<s>strike</s>` | ~~strike~~ |
| `[link](url)` | `<a href="url">link</a>` | [link](url) |
| `\`code\`` | `<code>code</code>` | `code` |

## Integration Points

### Main Message Handler
```python
# In handle_message()
mode = resolve_mode(update)
send_message(update, content, mode)
```

### Command Handlers
```python
# In command functions
send_message(update, "Response text", 'command_mode')
```

### Error Messages
```python
# For simple messages without formatting
send_simple_message(update, "Error occurred")
```

## Testing

Run the test suite to verify functionality:

```bash
python test_message_utils.py
```

Tests cover:
- HTML formatting conversion
- Mode detection accuracy
- CTA appending logic
- CTA stripping functionality
- HTML escaping
- Environment flag behavior

## Backward Compatibility

The refactoring maintains backward compatibility:
- All existing message sending still works
- Error handling preserved
- Whiskey emoji (🥃) still added to all messages
- System messages use simple text (no formatting)

## Benefits

1. **Clean Messages**: No more unwanted backslashes
2. **Contextual CTAs**: CTAs only when appropriate
3. **Better Formatting**: HTML provides more reliable formatting
4. **Mode Awareness**: Messages adapt to user intent
5. **Configurable**: Easy to enable/disable features
6. **Testable**: Comprehensive test coverage

## Migration Guide

### For New Messages
```python
# Old way
await update.message.reply_text(text, parse_mode='Markdown')

# New way
send_message(update, text, mode)
```

### For Simple Messages
```python
# Old way
await update.message.reply_text("Simple message")

# New way
send_simple_message(update, "Simple message")
```

### For Error Handling
```python
# Old way
await update.message.reply_text("Error occurred")

# New way
send_simple_message(update, "Error occurred")
```

## Summary

The refactoring successfully addresses both issues:

✅ **Fixed Markdown backslashes** - Switched to HTML parse mode  
✅ **Fixed stray CTAs** - Added conditional CTA appending based on mode  
✅ **Maintained functionality** - All existing features preserved  
✅ **Added flexibility** - Environment flags for configuration  
✅ **Improved testing** - Comprehensive test coverage  

The bot now sends clean, properly formatted messages with contextually appropriate CTAs.

