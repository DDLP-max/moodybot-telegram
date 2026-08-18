# -*- coding: utf-8 -*-
"""Canonical Suite — identity quality floor (asymmetric regression protection)."""

from inspector.canonical import run_canonical_suite


def test_canonical_suite_passes():
    summary = run_canonical_suite()
    assert summary["ok"], {
        r["id"]: r["failures"] for r in summary["results"] if not r["ok"]
    }
    assert summary["passed"] >= 6


def test_foreplay_and_prison_are_present():
    summary = run_canonical_suite(only=["foreplay", "prison"])
    assert summary["ok"]
    assert summary["total"] == 2


if __name__ == "__main__":
    test_canonical_suite_passes()
    test_foreplay_and_prison_are_present()
    print("ok")
