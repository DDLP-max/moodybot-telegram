# UTF-8 Encoding Enforcement

This project includes tools to ensure all text files are properly encoded as UTF-8 (no BOM) and that Python files have the correct encoding headers.

## Problem Solved

The original issue was a `SyntaxError: Non-UTF-8 code starting with '\xff'` error caused by files encoded as UTF-16 LE with BOM. This has been fixed by:

1. Converting all files to UTF-8 (no BOM)
2. Adding `# -*- coding: utf-8 -*-` headers to Python files
3. Creating automated tools to prevent regression

## Tools

### `scripts/ensure_utf8.py`

Main encoding enforcement script that:
- Scans all text files in the project
- Detects and converts various encodings to UTF-8
- Adds encoding headers to Python files
- Supports dry-run and fix modes

**Usage:**
```bash
# Dry run (check only)
python scripts/ensure_utf8.py --verbose

# Fix all encoding issues
python scripts/ensure_utf8.py --fix --verbose

# Check specific directory
python scripts/ensure_utf8.py --root /path/to/project --fix
```

### `scripts/print_file_encoding.py`

Debugging tool to inspect file encodings:
- Shows detected encoding
- Displays first few bytes in hex
- Provides text preview

**Usage:**
```bash
python scripts/print_file_encoding.py build_system_prompt.py
python scripts/print_file_encoding.py file1.py file2.py
```

## File Types Processed

The script processes these file extensions:
- `.py`, `.md`, `.json`, `.yml`, `.yaml`, `.txt`
- `.ini`, `.toml`, `.js`, `.ts`, `.tsx`
- `.css`, `.html`, `.mdx`, `.sh`, `.cfg`

## Directories Skipped

- `.git`, `.venv`, `venv`, `node_modules`
- `dist`, `build`, `__pycache__`
- `.mypy_cache`, `.pytest_cache`
- Binary files (images, archives, executables)

## Encoding Conversions

The script handles these encoding conversions:
- UTF-8 with BOM → UTF-8 (no BOM)
- UTF-16 LE/BE → UTF-8 (no BOM)
- Windows-1252/Latin-1 → UTF-8 (no BOM)
- Other encodings → UTF-8 (with error replacement)

## Python File Headers

For Python files, the script ensures:
- `# -*- coding: utf-8 -*-` header is present
- Header is placed after shebang (if present)
- No duplicate headers are added

## Pre-commit Integration

### Option 1: Pre-commit Framework

Install and configure:
```bash
pip install pre-commit
pre-commit install
```

The `.pre-commit-config.yaml` file is already configured.

### Option 2: Git Hooks

Manual setup:
```bash
cp githooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

## CI/CD Integration

GitHub Actions workflow (`.github/workflows/encoding-check.yml`) runs on:
- Push to main/master/develop branches
- Pull requests

The workflow will fail if any files have encoding issues.

## Verification

To verify all files are properly encoded:

```bash
# Check all files
python scripts/ensure_utf8.py --verbose

# Should show: "All files are properly encoded!"

# Check specific problematic files
python scripts/print_file_encoding.py build_system_prompt.py
```

## Fixed Files

The following files were converted from UTF-16 LE to UTF-8:
- `build_system_prompt.py`
- `build_system_prompt_enhanced.py`

All Python files now have proper UTF-8 encoding headers.

## Prevention

To prevent encoding issues in the future:

1. **Use the pre-commit hook** (recommended)
2. **Run the script before committing**:
   ```bash
   python scripts/ensure_utf8.py --fix
   ```
3. **Configure your editor** to save files as UTF-8 (no BOM)
4. **Use the CI check** to catch issues in pull requests

## Troubleshooting

### Common Issues

1. **"Non-UTF-8 code starting with '\xff'"**
   - File is encoded as UTF-16 with BOM
   - Run: `python scripts/ensure_utf8.py --fix`

2. **"SyntaxError: encoding problem"**
   - Python file missing encoding header
   - Run: `python scripts/ensure_utf8.py --fix`

3. **Files not being processed**
   - Check if file extension is in the supported list
   - Verify file is not in a skipped directory

### Debug Commands

```bash
# Check specific file encoding
python scripts/print_file_encoding.py problematic_file.py

# Dry run with verbose output
python scripts/ensure_utf8.py --verbose

# Check only Python files
python scripts/ensure_utf8.py --verbose | grep "\.py"
```

## Summary

✅ **Fixed**: UTF-16 LE encoding issues causing `\xff` errors  
✅ **Added**: UTF-8 encoding headers to all Python files  
✅ **Created**: Automated tools for detection and conversion  
✅ **Configured**: Pre-commit hooks and CI checks  
✅ **Documented**: Complete setup and usage instructions  

The project now has robust UTF-8 encoding enforcement that prevents regression and ensures compatibility across different systems.

