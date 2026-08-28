"""Built-in exporter registry.

Adding a format requires an exporter implementing the small protocol in
``base.py`` and one registration here; the curation pipeline and release
packager discover it automatically.
"""

from __future__ import annotations

from collections.abc import Iterable

from .anki import AnkiExporter
from .base import DeckArtifact, Exporter
from .mochi import MochiExporter, decode_transit_map, write_mochi


_EXPORTERS: dict[str, Exporter] = {
    exporter.name: exporter for exporter in (AnkiExporter(), MochiExporter())
}


def available_formats() -> tuple[str, ...]:
    return tuple(sorted(_EXPORTERS))


def get_exporter(name: str) -> Exporter:
    try:
        return _EXPORTERS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown export format: {name}") from exc


def select_exporters(names: Iterable[str] = ()) -> tuple[Exporter, ...]:
    selected = tuple(dict.fromkeys(names)) or available_formats()
    return tuple(get_exporter(name) for name in selected)


__all__ = [
    "DeckArtifact",
    "available_formats",
    "decode_transit_map",
    "get_exporter",
    "select_exporters",
    "write_mochi",
]
