# -*- coding: utf-8 -*-
"""python -m inspector seed | serve | import-log | rebuild | watch """

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


    if cmd == "capabilities":
        # python -m inspector capabilities [hidden_transaction|escalation_payoff|comic_premise]
        which = (args[1] if len(args) > 1 else "all").lower().replace("-", "_")
        from capability_detection import (
            detect_comic_premise,
            detect_escalation_payoff,
            detect_hidden_transaction,
        )

        samples = {
            "hidden_transaction": (
                "Management already knows what it wants but hires McKinsey to recommend it."
            ),
            "escalation_payoff": (
                "Then the actor scared the CFO. Then more budget. Then a pontoon boat."
            ),
            "comic_premise": (
                "Only 3 more years of bulking and cutting and I can begin phase one "
                "of looking women in the eyes"
            ),
            "none": "How do I replace a fiber connector?",
        }
        ok = True
        if which in {"all", "hidden_transaction"}:
            ht = detect_hidden_transaction(samples["hidden_transaction"])
            print(
                f"hidden_transaction active={int(ht.active)} confidence={ht.confidence:.2f} "
                f"tx={ht.actual_transaction}"
            )
            ok = ok and ht.active
            ht_none = detect_hidden_transaction(samples["none"])
            print(f"hidden_transaction_neg active={int(ht_none.active)}")
            ok = ok and not ht_none.active
        if which in {"all", "escalation_payoff"}:
            ep = detect_escalation_payoff(samples["escalation_payoff"])
            print(
                f"escalation_payoff active={int(ep.active)} confidence={ep.confidence:.2f} "
                f"payoff={ep.concrete_payoff_hint}"
            )
            ok = ok and ep.active
        if which in {"all", "comic_premise"}:
            comic = detect_comic_premise(samples["comic_premise"])
            print(
                f"comic_premise active={int(comic.active)} confidence={comic.confidence:.2f} "
                f"signals={comic.signals}"
            )
            ok = ok and comic.active and comic.never_cure
            comic_none = detect_comic_premise(samples["none"])
            print(f"comic_premise_neg active={int(comic_none.active)}")
            ok = ok and not comic_none.active
        raise SystemExit(0 if ok else 1)

    print(
        "Usage:\n"
        "  python -m inspector seed\n"
        "  python -m inspector serve [port]\n"
        "  python -m inspector import-log [path] [--since YYYY-MM-DD]\n"
        "  python -m inspector rebuild [path] [--keep-seeds]\n"
        "  python -m inspector watch [path]\n"
        "  python -m inspector capabilities "
        "[hidden_transaction|escalation_payoff|comic_premise]"
    )


if __name__ == "__main__":
    main()
