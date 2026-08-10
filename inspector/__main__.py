# -*- coding: utf-8 -*-
"""python -m inspector seed | serve | import-log | rebuild | watch"""

from __future__ import annotations

import sys
import time
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    args = list(argv or sys.argv[1:])
    cmd = (args[0] if args else "help").lower()

    if cmd == "seed":
        from .seed import main as seed_main

        seed_main()
        return

    if cmd == "serve":
        from flask import redirect, url_for
        from main import app

        port = int(args[1]) if len(args) > 1 else 5055

        def _inspector_root_redirect():
            return redirect(url_for("inspector_home"))

        app.view_functions["index"] = _inspector_root_redirect
        print(f"Moody Inspector → http://127.0.0.1:{port}/inspector")
        print("(root / redirects there)")
        app.run(host="127.0.0.1", port=port, debug=False)
        return

    if cmd == "import-log":
        from .store import import_log

        path = args[1] if len(args) > 1 else "moodybot_log.txt"
        since = None
        if "--since" in args:
            i = args.index("--since")
            since = args[i + 1] if i + 1 < len(args) else None
        if not Path(path).exists():
            # common aliases
            for alt in ("moodybot.log", "moodybot_log.txt"):
                if Path(alt).exists():
                    path = alt
                    break
        stats = import_log(path, since=since, merge_live=True)
        print(f"import-log {path}: {stats}")
        return

    if cmd == "rebuild":
        from .store import rebuild

        log_path = None
        keep_seeds = "--keep-seeds" in args
        for a in args[1:]:
            if a.startswith("--"):
                continue
            log_path = a
            break
        stats = rebuild(log_path, keep_seeds=keep_seeds)
        print(f"rebuild: {stats}")
        print("Hall of Fame preserved.")
        return

    if cmd == "watch":
        from .store import import_log

        path = Path(args[1] if len(args) > 1 else "moodybot_log.txt")
        if not path.exists():
            path = Path("moodybot.log")
        print(f"watching {path} (Ctrl+C to stop)")
        last = path.stat().st_mtime if path.exists() else 0.0
        while True:
            time.sleep(2.0)
            if not path.exists():
                continue
            mtime = path.stat().st_mtime
            if mtime > last:
                last = mtime
                stats = import_log(path, merge_live=True)
                print(f"reloaded: {stats}")
        return

    print(
        "Usage:\n"
        "  python -m inspector seed\n"
        "  python -m inspector serve [port]\n"
        "  python -m inspector import-log [path] [--since YYYY-MM-DD]\n"
        "  python -m inspector rebuild [path] [--keep-seeds]\n"
        "  python -m inspector watch [path]"
    )


if __name__ == "__main__":
    main()
