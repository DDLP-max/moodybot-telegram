# -*- coding: utf-8 -*-
"""Run the one-shot publish commands once inside the service.

The approved file is written from the stored dry-run text. Preview runs
first. The confirm command runs only when that preview shows @MoodyBotAI,
write evidence, and the same text. A later boot does not run either command.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable, List, Optional

from x_integration.dry_run import CONFIRMED_USER_ID, CONFIRMED_USERNAME, DRY_RUN_FILENAME
from x_integration.publish_once import stored_draft
from x_integration.state import state_dir

POST_ID = "2119262820428865635"
MARKER_NAME = "publish-once-2119262820428865635.json"
DRAFT_NAME = "approved-reply.txt"
Command = Callable[[List[str]], dict]


def run_operator_publish(root: Optional[Path] = None, *, run_command: Optional[Command] = None) -> dict:
    directory = Path(root) if root is not None else state_dir()[0]
    marker = directory / MARKER_NAME
    if marker.is_file():
        return _read_marker(marker)
    directory.mkdir(parents=True, exist_ok=True)
    _write_marker(marker, {"state": "started", "posted": False})
    stored = stored_draft(directory / DRY_RUN_FILENAME, POST_ID)
    draft_path = directory / DRAFT_NAME
    if not stored:
        return _write_marker(marker, {"state": "refused", "reason": "missing_draft", "posted": False})
    draft_path.write_text(stored, encoding="utf-8")
    command = run_command or _module_command
    preview = command(["--post-id", POST_ID, "--draft-file", str(draft_path)])
    preview_ok = _preview_passes(preview, stored)
    result = {
        "state": "preview",
        "posted": False,
        "preview_ok": preview_ok,
        "account": preview.get("account") or "",
        "user_id": preview.get("user_id") or "",
        "write_evidence": preview.get("write_evidence") or "",
        "preview_status": preview.get("status") or "",
        "preview_reason": preview.get("reason") or "",
        "reply_text": preview.get("reply_text") or "",
        "draft_sha256": preview.get("draft_sha256") or "",
        "post_id": POST_ID,
    }
    if not preview_ok:
        result["state"] = "preview_failed"
        return _write_marker(marker, result)
    published = command(
        [
            "--post-id",
            POST_ID,
            "--draft-file",
            str(draft_path),
            "--confirm",
            f"POST:{POST_ID}",
        ]
    )
    result.update(
        {
            "state": "finished",
            "posted": published.get("posted") == "true" or published.get("status") == "posted",
            "publish_status": published.get("status") or "",
            "publish_reason": published.get("reason") or "",
            "x_reply_id": published.get("x_reply_id") or "",
            "publish_exit_code": published.get("exit_code"),
        }
    )
    if result["publish_status"] == "ambiguous":
        result["state"] = "ambiguous"
    return _write_marker(marker, result)


def _preview_passes(preview: dict, stored: str) -> bool:
    return (
        preview.get("exit_code") == 0
        and preview.get("status") == "preview"
        and preview.get("posted") == "false"
        and preview.get("account") == f"@{CONFIRMED_USERNAME}"
        and preview.get("user_id") == CONFIRMED_USER_ID
        and preview.get("write_evidence") in {"tweet.write", "x-access-level"}
        and preview.get("post_id") == POST_ID
        and preview.get("reply_text") == stored
    )


def _module_command(args: List[str]) -> dict:
    completed = subprocess.run(
        [sys.executable, "-m", "x_integration.publish_once", *args],
        cwd=str(Path(__file__).resolve().parents[1]),
        capture_output=True,
        text=True,
        timeout=90,
        env=os.environ.copy(),
        check=False,
    )
    parsed = _parse_output(completed.stdout)
    parsed["exit_code"] = completed.returncode
    return parsed


def _parse_output(stdout: str) -> dict:
    fields = {}
    reply = None
    for line in stdout.splitlines():
        if reply is not None:
            reply.append(line)
            continue
        if line == "reply_text:":
            reply = []
            continue
        if ": " in line:
            key, value = line.split(": ", 1)
            fields[key] = value
    if reply is not None:
        fields["reply_text"] = "\n".join(reply)
    return fields


def _read_marker(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {"state": "started", "posted": False}
    if isinstance(data, dict):
        data["rerun"] = False
        return data
    return {"state": "started", "posted": False, "rerun": False}


def _write_marker(path: Path, result: dict) -> dict:
    path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return result
