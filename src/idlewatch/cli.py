"""idlewatch read <save> | idlewatch list [--saves-dir DIR]: print Melvor Idle 2 saves as JSON, read-only."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import brotli

from . import __version__
from .save import load

GAME = Path("Games By Malcs", "Melvor Idle 2")


def default_saves_dir() -> Path | None:
    """The game's data folder on macOS and Windows; None elsewhere (pass --saves-dir)."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / GAME
    if sys.platform == "win32" and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / GAME
    return None


def find_saves(root: Path) -> list[dict]:
    """A summary of every save_*.sav under root (normally steam/<steamid>/saves/), sorted by path."""
    found = []
    for path in sorted(root.rglob("save_*.sav")):
        try:
            save = load(path)
        except (OSError, ValueError, brotli.error) as error:
            found.append({"path": str(path), "error": str(error)})
            continue
        found.append({"path": str(path), **{key: save[key] for key in
                                            ("uuid", "name", "mode", "saved_at", "total_level")}})
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="idlewatch", description="Read Melvor Idle 2 saves, never write them.")
    parser.add_argument("--version", action="version", version=f"idlewatch {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    read = commands.add_parser("read", help="print one save decoded as JSON")
    read.add_argument("save", type=Path)
    listing = commands.add_parser("list", help="find saves and print a summary of each as JSON")
    listing.add_argument("--saves-dir", type=Path, help="folder to search (default: the game's data folder)")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # character names are UTF-8, whatever the console code page

    if args.command == "read":
        try:
            result = load(args.save)
        except (OSError, ValueError, brotli.error) as error:
            print(f"idlewatch: cannot read {args.save}: {error}", file=sys.stderr)
            return 1
    else:
        root = args.saves_dir or default_saves_dir()
        if root is None:
            parser.error("no default saves folder on this platform: pass --saves-dir")
        if not root.is_dir():
            print(f"idlewatch: no saves folder at {root}", file=sys.stderr)
            return 1
        result = find_saves(root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
