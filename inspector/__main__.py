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
        from main import app

        port = int(args[1]) if len(args) > 1 else 5055
        print(f"Moody Inspector → http://127.0.0.1:{port}/inspector")
        app.run(host="127.0.0.1", port=port, debug=False)
        return
    print("Usage: python -m inspector seed | serve [port]")


if __name__ == "__main__":
    main()
