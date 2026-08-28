"""Command-line interface for the curator."""

from __future__ import annotations

import argparse

from .curator import LEVELS, build, fetch, json_dump, package_release, sha256, verify
from .exporters import available_formats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reproducibly curate JLPT data and export deterministic flashcard decks."
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    for command in ("fetch", "build", "all", "verify", "package"):
        item = subcommands.add_parser(command)
        item.add_argument("--level", action="append", choices=LEVELS, default=[])
        if command != "fetch":
            item.add_argument("--format", action="append", choices=available_formats(), default=[])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    levels = tuple(args.level or ["N5"])
    formats = tuple(getattr(args, "format", ()))
    if args.command in {"fetch", "all"}:
        fetch(levels)
    if args.command in {"build", "all"}:
        print(json_dump([build(level, formats) for level in levels]), end="")
    elif args.command == "verify":
        print(json_dump([verify(level, formats) for level in levels]), end="")
    elif args.command == "package":
        paths = package_release(levels, formats)
        print(
            json_dump(
                [
                    {"file": path.name, "sha256": sha256(path), "bytes": path.stat().st_size}
                    for path in paths
                ]
            ),
            end="",
        )
    return 0
