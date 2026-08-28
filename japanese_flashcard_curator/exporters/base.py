"""Format-neutral exporter contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, Sequence


Record = dict[str, Any]


@dataclass(frozen=True)
class DeckArtifact:
    """One generated deck file plus enough metadata to validate it."""

    format: str
    scope: str
    path: Path
    decks: tuple[tuple[str, int], ...]

    @property
    def card_count(self) -> int:
        return sum(count for _, count in self.decks)

    def to_report(self, sha256: str) -> dict[str, Any]:
        return {
            "format": self.format,
            "scope": self.scope,
            "file": self.path.name,
            "cards": self.card_count,
            "decks": [{"name": name, "cards": count} for name, count in self.decks],
            "sha256": sha256,
            "bytes": self.path.stat().st_size,
        }

    @classmethod
    def from_report(cls, output_dir: Path, value: dict[str, Any]) -> "DeckArtifact":
        return cls(
            format=value["format"],
            scope=value["scope"],
            path=output_dir / value["file"],
            decks=tuple((deck["name"], deck["cards"]) for deck in value["decks"]),
        )


class Exporter(Protocol):
    name: str
    extension: str

    def export(
        self,
        level: str,
        vocabulary: Sequence[Record],
        kanji: Sequence[Record],
        output_dir: Path,
    ) -> list[DeckArtifact]: ...

    def validate(self, artifact: DeckArtifact) -> list[str]: ...
