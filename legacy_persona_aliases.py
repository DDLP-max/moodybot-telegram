# -*- coding: utf-8 -*-
"""Legacy persona/slash aliases → EI capability bundles.

Deprecated identifiers remain for backwards compatibility.
Runtime should prefer capability names from dynamic intelligence routing.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

_ALIAS_PATH = Path(__file__).resolve().parent / "legacy_persona_aliases.json"


def load_aliases() -> Dict[str, Any]:
    with open(_ALIAS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_alias(name: str) -> Optional[Dict[str, Any]]:
    key = name.strip().lower().lstrip("/")
    aliases = load_aliases()
    return aliases.get(key)


def bundle_for_command(command: str) -> Dict[str, List[str]]:
    """Map a slash command to capabilities / intervention / voice."""
    resolved = resolve_alias(command) or {}
    return {
        "capabilities": list(resolved.get("capabilities") or []),
        "intervention": list(resolved.get("intervention") or []),
        "voice": list(resolved.get("voice") or []),
        "deprecated": bool(resolved.get("deprecated", False)),
        "legacy_command": command if command.startswith("/") else f"/{command}",
    }
