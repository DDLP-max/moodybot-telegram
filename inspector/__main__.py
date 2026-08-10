# -*- coding: utf-8 -*-
"""python -m inspector seed | serve"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> None:
    args = list(argv or sys.argv[1:])
    cmd = (args[0] if args else "help").lower()
    if cmd == "seed":
        from .seed import main as seed_main

        seed_main()
        return
    if cmd == "serve":
        # Thin wrapper — prefer Flask app routes on main.py
        from flask import redirect, url_for
        from main import app

        port = int(args[1]) if len(args) > 1 else 5055

        # Local serve: `/` should open Inspector, not the bot admin index.
        def _inspector_root_redirect():
            return redirect(url_for("inspector_home"))

        app.view_functions["index"] = _inspector_root_redirect

        print(f"Moody Inspector → http://127.0.0.1:{port}/inspector")
        print(f"(root / redirects there)")
        app.run(host="127.0.0.1", port=port, debug=False)
        return
    print("Usage: python -m inspector seed | serve [port]")


if __name__ == "__main__":
    main()
