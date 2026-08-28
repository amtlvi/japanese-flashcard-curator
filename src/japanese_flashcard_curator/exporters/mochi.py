"""Deterministic Mochi Transit-JSON exporter."""

from __future__ import annotations

import json
import zipfile
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from .base import DeckArtifact, Record


def transit_map(items: Sequence[tuple[str, object]]) -> list[object]:
    out: list[object] = ["^ "]
    for key, value in items:
        out.extend((f"~:{key}", value))
    return out


def transit_string(value: str) -> str:
    return f"~{value}" if value.startswith(("~", "^", "`")) else value


def raw_code_block(values: Iterable[str]) -> list[str]:
    cleaned = list(dict.fromkeys(" ".join(value.split()) for value in values if value.strip()))
    return ["```text", *(cleaned or ["(no sourced example available)"]), "```"]


def vocabulary_card(record: Record) -> str:
    lines = [
        f"# {record['written']['without_furigana']}",
        "",
        "---",
        "",
        f"# {record['written']['with_furigana']}",
        "",
        f"**Reading:** {record['reading']['primary']}",
        "",
        "**Meaning**",
        "",
        *(f"- {meaning}" for meaning in record["meanings"]),
    ]
    if record["parts_of_speech"]:
        lines += ["", "**Part of speech:** " + "; ".join(p["label"] for p in record["parts_of_speech"])]
    if record["examples"]:
        lines += ["", "**Examples**", ""]
        for example in record["examples"]:
            lines += [example["japanese_furigana"], f"_{example['english']}_", ""]
        while lines and not lines[-1]:
            lines.pop()
    lines += ["", "**Copyable Japanese (raw)**", ""]
    lines += raw_code_block(example["japanese_raw"] for example in record["examples"])
    if not record["examples"]:
        lines += ["", f"Lookup: `{record['written']['lookup_text']}`"]
    lines += ["", f"JLPT {record['level']} · Order {record['order']} · {'Common' if record['common'] else 'Standard'}"]
    return "\n".join(lines)


def kanji_card(record: Record) -> str:
    lines = [f"# {record['character']}", "", "---", "", f"# {record['character']}"]
    lines += ["", "**Meanings:** " + "; ".join(record["meanings"])]
    if record["readings"]["onyomi"]:
        lines += ["", "**On’yomi:** " + "、".join(record["readings"]["onyomi"])]
    if record["readings"]["kunyomi"]:
        lines += ["", "**Kun’yomi:** " + "、".join(record["readings"]["kunyomi"])]
    stats = [f"Strokes: {record['strokes']}"]
    if record["grade"] is not None:
        stats.append(f"Grade: {record['grade']}")
    if record["frequency_rank"] is not None:
        stats.append(f"Frequency: #{record['frequency_rank']}")
    lines += ["", " · ".join(stats), "", "**Visible components (KRADFILE):**"]
    if record["components"]:
        lines += [
            "、".join(
                component["symbol"]
                + (f" ({', '.join(component['meanings'])})" if component["meanings"] else "")
                for component in record["components"]
            )
        ]
    else:
        lines += ["Atomic in KRADFILE"]
    if record["example_words"]:
        lines += ["", "**Example words**", ""]
        for word in record["example_words"]:
            lines.append(f"- {word['written_furigana']} — {'; '.join(word['meanings'])}")
    lines += ["", "**Copyable Japanese (raw)**", ""]
    lines += raw_code_block([record["character"], *(word["written_raw"] for word in record["example_words"])])
    lines += ["", f"JLPT {record['level']} · Frequency order {record['order']}"]
    return "\n".join(lines)


def write_mochi(path: Path, decks: Sequence[tuple[str, Sequence[str]]]) -> None:
    encoded_decks = []
    for deck_name, cards in decks:
        width = max(6, len(str(len(cards))))
        encoded_cards = [
            transit_map((("content", transit_string(content)), ("pos", f"{index:0{width}d}")))
            for index, content in enumerate(cards, start=1)
        ]
        encoded_decks.append(transit_map((("name", transit_string(deck_name)), ("cards", encoded_cards))))
    payload = transit_map((("version", 2), ("decks", encoded_decks)))
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    info = zipfile.ZipInfo("data.json", date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    temporary = path.with_suffix(path.suffix + ".tmp")
    with zipfile.ZipFile(temporary, "w") as archive:
        archive.writestr(info, data)
    temporary.replace(path)


def decode_transit_map(value: object) -> dict[str, object]:
    if not isinstance(value, list) or not value or value[0] != "^ " or len(value) % 2 != 1:
        raise AssertionError("invalid Transit map")
    return {value[index][2:]: value[index + 1] for index in range(1, len(value), 2)}


class MochiExporter:
    name = "mochi"
    extension = ".mochi"

    def export(
        self,
        level: str,
        vocabulary: Sequence[Record],
        kanji: Sequence[Record],
        output_dir: Path,
    ) -> list[DeckArtifact]:
        vocabulary_deck = (f"JLPT {level} Vocabulary", [vocabulary_card(record) for record in vocabulary])
        kanji_deck = (f"JLPT {level} Kanji", [kanji_card(record) for record in kanji])
        stem = f"jlpt_{level.lower()}"
        specs = (
            ("vocabulary", output_dir / f"{stem}_vocabulary.mochi", (vocabulary_deck,)),
            ("kanji", output_dir / f"{stem}_kanji.mochi", (kanji_deck,)),
            ("complete", output_dir / f"{stem}_complete.mochi", (vocabulary_deck, kanji_deck)),
        )
        artifacts = []
        for scope, path, decks in specs:
            write_mochi(path, decks)
            artifacts.append(
                DeckArtifact(
                    format=self.name,
                    scope=scope,
                    path=path,
                    decks=tuple((name, len(cards)) for name, cards in decks),
                )
            )
        return artifacts

    def validate(self, artifact: DeckArtifact) -> list[str]:
        errors: list[str] = []
        try:
            with zipfile.ZipFile(artifact.path) as archive:
                if archive.namelist() != ["data.json"] or archive.testzip() is not None:
                    return [f"invalid Mochi archive: {artifact.path.name}"]
                root = decode_transit_map(json.loads(archive.read("data.json")))
        except (OSError, zipfile.BadZipFile, json.JSONDecodeError, AssertionError) as exc:
            return [f"invalid Mochi archive {artifact.path.name}: {exc}"]
        if root.get("version") != 2:
            errors.append(f"wrong Mochi version: {artifact.path.name}")
        decks = root.get("decks", [])
        if len(decks) != len(artifact.decks):
            errors.append(f"wrong Mochi deck count: {artifact.path.name}")
            return errors
        for encoded, (expected_name, expected_count) in zip(decks, artifact.decks):
            deck = decode_transit_map(encoded)
            name = str(deck["name"]).removeprefix("~")
            cards = deck["cards"]
            positions = [decode_transit_map(card)["pos"] for card in cards]
            if name != expected_name or len(cards) != expected_count:
                errors.append(f"wrong Mochi contents: {artifact.path.name}/{expected_name}")
            if positions != sorted(positions) or len(positions) != len(set(positions)):
                errors.append(f"invalid Mochi positions: {artifact.path.name}/{expected_name}")
        return errors
