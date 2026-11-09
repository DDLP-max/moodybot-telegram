# -*- coding: utf-8 -*-
"""The operator command runs preview first and does not repeat a publish."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from x_integration.operator_publish import POST_ID, run_operator_publish
from x_integration.state import MentionLedger

DRAFT = "Approved reply text. 🥃"


def _ledger(root: Path) -> None:
    side = MentionLedger(root / "dry-run.sqlite")
    event_id = f"dry-run:{POST_ID}"
    side.claim(event_id, POST_ID, "2082957781293035520", "2119097552092250463")
    side.finish(event_id, status="dry_run", reply_text=DRAFT, post_id=POST_ID)


def _preview(stored: str) -> dict:
    return {
        "exit_code": 0,
        "status": "preview",
        "posted": "false",
        "account": "@MoodyBotAI",
        "user_id": "1912252811469025282",
        "write_evidence": "tweet.write",
        "post_id": POST_ID,
        "reply_text": stored,
        "draft_sha256": "abc",
    }


def test_failed_preview_does_not_publish_and_does_not_rerun():
    calls = []

    def run_command(args):
        calls.append(args)
        return {"exit_code": 2, "status": "refused", "posted": "false", "reason": "tweet_write_unverified"}

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        _ledger(root)
        first = run_operator_publish(root, run_command=run_command)
        second = run_operator_publish(root, run_command=run_command)
        assert (root / "approved-reply.txt").read_text(encoding="utf-8") == DRAFT
    assert first["state"] == "preview_failed"
    assert first["posted"] is False
    assert len(calls) == 1
    assert "--confirm" not in calls[0]
    assert second["rerun"] is False
    assert len(calls) == 1


def test_passing_preview_publishes_once():
    calls = []

    def run_command(args):
        calls.append(list(args))
        if "--confirm" not in args:
            return _preview(DRAFT)
        return {
            "exit_code": 0,
            "status": "posted",
            "posted": "true",
            "x_reply_id": "555",
            "post_id": POST_ID,
        }

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        _ledger(root)
        result = run_operator_publish(root, run_command=run_command)
        again = run_operator_publish(root, run_command=run_command)
    assert result["posted"] is True
    assert result["x_reply_id"] == "555"
    assert result["reply_text"] == DRAFT
    assert calls[1][-1] == f"POST:{POST_ID}"
    assert again["rerun"] is False
    assert len(calls) == 2


def test_ambiguous_publish_is_not_rerun():
    calls = []

    def run_command(args):
        calls.append(list(args))
        if "--confirm" not in args:
            return _preview(DRAFT)
        return {"exit_code": 3, "status": "ambiguous", "posted": "false", "reason": "ambiguous"}

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        _ledger(root)
        first = run_operator_publish(root, run_command=run_command)
        second = run_operator_publish(root, run_command=run_command)
        saved = json.loads((root / "publish-once-2119262820428865635.json").read_text(encoding="utf-8"))
    assert first["state"] == "ambiguous"
    assert first["posted"] is False
    assert saved["state"] == "ambiguous"
    assert second["rerun"] is False
    assert len(calls) == 2


if __name__ == "__main__":
    test_failed_preview_does_not_publish_and_does_not_rerun()
    test_passing_preview_publishes_once()
    test_ambiguous_publish_is_not_rerun()
    print("operator publish ok")
