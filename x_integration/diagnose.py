# -*- coding: utf-8 -*-
"""Read-only ledger check for a Render shell.

Run from the service directory:

    python -m x_integration.diagnose

This does not open a route, create the database, or print secrets.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from x_integration.state import ledger_path, state_dir


def report() -> dict:
    root, source = state_dir()
    path = ledger_path()
    exists = path.is_file()
    accessible = False
    access = "missing"
    tables: list[str] = []
    if exists:
        accessible, access, tables = _probe(path)
    disk = _disk_status(root)
    return {
        "x_state_dir": str(root),
        "x_state_dir_source": source,
        "database_path": str(path),
        "database_filename": path.name,
        "file_exists": exists,
        "database_accessible": accessible,
        "database_access": access,
        "tables": ",".join(tables),
        **disk,
    }


def format_report(info: dict) -> str:
    lines = [f"{key}={info[key]}" for key in info]
    return "\n".join(lines)


def main() -> int:
    print(format_report(report()))
    return 0


def _probe(path: Path) -> tuple[bool, str, list[str]]:
    try:
        conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    except sqlite3.Error:
        return False, "unreadable", []
    try:
        conn.execute("SELECT 1").fetchone()
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).fetchall()
    except sqlite3.Error:
        return False, "unreadable", []
    finally:
        conn.close()
    tables = [str(row[0]) for row in rows if not str(row[0]).startswith("sqlite_")]
    return True, "ok", tables


def _disk_status(root: Path) -> dict:
    target = os.path.abspath(root)
    mounts = _mounts()
    var_data = ""
    var_fstype = ""
    best_point = ""
    best_fstype = ""
    for point, fstype in mounts:
        if point == "/var/data":
            var_data = point
            var_fstype = fstype
        if _is_under(target, point) and len(point) > len(best_point):
            best_point = point
            best_fstype = fstype
    on_data_disk = best_point == "/var/data" or best_point.startswith("/var/data/")
    return {
        "disk_mounted": bool(var_data),
        "disk_mount_path": var_data,
        "disk_fstype": var_fstype,
        "database_mount_point": best_point,
        "database_mount_fstype": best_fstype,
        "database_on_mounted_disk": on_data_disk,
    }


def _mounts() -> list[tuple[str, str]]:
    proc = Path("/proc/mounts")
    if not proc.is_file():
        return []
    found = []
    for line in proc.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        point = parts[1].replace("\\040", " ")
        found.append((point, parts[2]))
    return found


def _is_under(path: str, mount: str) -> bool:
    if not mount or mount == "/":
        return False
    mount = mount.rstrip("/")
    return path == mount or path.startswith(mount + os.sep) or path.startswith(mount + "/")


if __name__ == "__main__":
    raise SystemExit(main())
