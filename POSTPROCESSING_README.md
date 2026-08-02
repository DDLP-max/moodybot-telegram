# MoodyBot Post-Processing Pipeline

This document describes the new post-processing pipeline implemented to prevent unwanted autocorrections on bot outputs, particularly preserving proper nouns like "Cialdini".

## Overview

The post-processing pipeline implements explicit stages with logging and proper-noun preservation to ensure that bot outputs maintain their intended meaning and formatting.

## Architecture

### Pipeline Stages

1. **Stage A: Format Markdown** (`format_markdown`)
   - Only escapes MarkdownV2 special characters
   - No lexical changes to content

2. **Stage B: Apply Output Filters** (`apply_output_filters`)
   - Respects `SPELLCHECK_BOT_OUTPUT` environment variable
   - Default: `false` (no spellcheck on bot outputs)
   - When enabled: still protects whitelisted proper nouns

### Key Components

- **`postprocessing.py`**: Main post-processing module
- **`proper_nouns.json`**: Configurable whitelist of proper nouns
- **`test_postprocessing.py`**: Unit tests
- **`test_bot_integration.py`**: Integration tests

## Configuration

### Environment Variables

- `SPELLCHECK_BOT_OUTPUT`: Set to `false` (default) to disable spellcheck on bot outputs
- `DEBUG`: Set to `bot:postprocess` to enable verbose logging

### Proper Noun Whitelist

The whitelist is managed in `proper_nouns.json` and includes:
- `Cialdini`, `Kahneman`, `Tversky` (psychologists)
- `MoodyBot`, `Ogilvy`, `Grok` (brands)
- `Da Nang`, `Ala Wai`, `Donna Walden` (places/people)
- And more...

## Usage

### Basic Usage

```python
from postprocessing import process_bot_output, process_user_input

# Process bot output (preserves proper nouns, no spellcheck by default)
bot_response = process_bot_output(raw_llm_output)

# Process user input (soft spellcheck with hints)
user_input = process_user_input(raw_user_input)
```

### Advanced Usage

```python
from postprocessing import (
    preserve_whitelisted_tokens, 
    restore_whitelisted_tokens,
    is_whitelisted_token
)

# Check if a token is whitelisted
if is_whitelisted_token("Cialdini"):
    print("Token is protected")

# Preserve tokens during custom processing
protected_text, tokens = preserve_whitelisted_tokens(text)
# ... do custom processing ...
restored_text = restore_whitelisted_tokens(protected_text, tokens)
```

## Testing

### Unit Tests

```bash
python test_postprocessing.py
```

### Integration Tests

```bash
python test_bot_integration.py
```

### Test Coverage

- ✅ Proper noun preservation
- ✅ MarkdownV2 escaping
- ✅ Environment variable handling
- ✅ Debug logging
- ✅ Edge cases (empty input, whitespace)

## Implementation Details

### Proper Noun Protection

The system uses a two-stage approach:

1. **Whitelist Check**: Before any processing, check if tokens match the whitelist
2. **Preserve/Restore**: Use placeholder system to protect tokens during processing

### MarkdownV2 Escaping

Only escapes characters that are special in MarkdownV2:
- `_`, `*`, `[`, `]`, `(`, `)`, `~`, `` ` ``, `>`, `#`, `+`, `=`, `|`, `{`, `}`, `.`, `!`, `-`

### Debug Logging

When `DEBUG=bot:postprocess` is set, the system logs:
- Raw input vs final output
- Stage-by-stage processing
- First detected change and context

## Migration from Old System

The old text processing pipeline has been replaced:

**Before:**
```python
content = grammar_polish(content)  # This could modify proper nouns
```

**After:**
```python
content = process_bot_output(raw_content)  # Preserves proper nouns
```

## Deployment

### Production Settings

```bash
SPELLCHECK_BOT_OUTPUT=false
DEBUG=bot:postprocess
```

### Development Settings

```bash
SPELLCHECK_BOT_OUTPUT=true  # For testing spellcheck behavior
DEBUG=bot:postprocess
```

## Troubleshooting

### Common Issues

1. **Proper nouns being modified**: Check that they're in `proper_nouns.json`
2. **Markdown not rendering**: Check that special characters are properly escaped
3. **Debug logs not showing**: Ensure `DEBUG=bot:postprocess` is set

### Debugging

Enable debug logging to see the processing stages:

```python
import os
os.environ['DEBUG'] = 'bot:postprocess'
```

## Future Enhancements

- Soft spellcheck for user input with confidence-based hints
- Dynamic whitelist updates via API
- Performance monitoring for post-processing stages
- A/B testing for different processing strategies

## Contributing

When adding new proper nouns to the whitelist:

1. Add to `proper_nouns.json`
2. Update tests in `test_postprocessing.py`
3. Run integration tests
4. Update this documentation

## Changelog

### v1.0.0 (2024-01-01)
- Initial implementation of post-processing pipeline
- Proper noun whitelist system
- MarkdownV2 escaping
- Debug logging
- Unit and integration tests

