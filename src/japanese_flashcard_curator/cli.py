"""Command-line interface for the curator."""

from __future__ import annotations

import argparse
from pathlib import Path

from .curator import LEVELS, build, fetch, json_dump, package_release, sha256, verify
from .exporters import available_formats
from .exporters.mochi import prepare_mochi_update


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
    upgrade = subcommands.add_parser(
        "mochi-upgrade", description="Build an in-place Mochi update without replacing review history."
    )
    upgrade.add_argument("existing", type=Path, help="native .mochi export of the imported deck")
    upgrade.add_argument("release", type=Path, help="new .mochi release file")
    upgrade.add_argument("--output", type=Path, default=Path("mochi-update.mochi"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "mochi-upgrade":
        print(json_dump(prepare_mochi_update(args.existing, args.release, args.output)), end="")
        return 0
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
