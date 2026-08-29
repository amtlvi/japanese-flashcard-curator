"""Deterministic Mochi Transit-JSON export and upgrade support."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from collections import defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from .base import DeckArtifact, Record


TAG_LIKE = re.compile(r"(?<!\S)#[^\s#]+")


def transit_map(items: Sequence[tuple[str, object]]) -> list[object]:
    out: list[object] = ["^ "]
    for key, value in items:
        out.extend((f"~:{key}", value))
    return out


def transit_string(value: str) -> str:
    return f"~{value}" if value.startswith(("~", "^", "`")) else value


def transit_keyword(value: str) -> str:
    return f"~:{value}"


def stable_id(kind: str, value: str) -> str:
    """Return a Mochi-compatible globally stable ID."""
    return "JFC" + hashlib.sha256(f"{kind}:{value}".encode()).hexdigest()[:17]


def raw_code_block(values: Iterable[str]) -> list[str]:
    cleaned = list(dict.fromkeys(" ".join(value.split()) for value in values if value.strip()))
    return ["```text", *(cleaned or ["(no sourced example available)"]), "```"]


def escape_tag_like_markdown(markdown: str) -> str:
    """Escape Mochi tag syntax outside fenced literal-text blocks."""
    lines: list[str] = []
    fenced = False
    for line in markdown.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            lines.append(line)
        else:
            lines.append(line if fenced else TAG_LIKE.sub(lambda match: "\\" + match.group(), line))
    return "\n".join(lines)


def has_tag_like_markdown(markdown: str) -> bool:
    """Detect unescaped Mochi tags while ignoring literal fenced text."""
    fenced = False
    for line in markdown.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced and TAG_LIKE.search(line):
            return True
    return False


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
    return escape_tag_like_markdown("\n".join(lines))


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
        stats.append(f"Frequency rank: {record['frequency_rank']}")
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
    return escape_tag_like_markdown("\n".join(lines))


def _write_transit_archive(path: Path, payload: list[object]) -> None:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    info = zipfile.ZipInfo("data.json", date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    temporary = path.with_suffix(path.suffix + ".tmp")
    with zipfile.ZipFile(temporary, "w") as archive:
        archive.writestr(info, data)
    temporary.replace(path)


def write_mochi(
    path: Path,
    decks: Sequence[tuple[str, Sequence[str | tuple[str, str]]]],
) -> None:
    """Write an initial-import package that also has stable update identities."""
    encoded_decks = []
    encoded_cards = []
    for deck_name, cards in decks:
        deck_id = stable_id("deck", deck_name)
        encoded_decks.append(
            transit_map((("id", transit_keyword(deck_id)), ("name", transit_string(deck_name))))
        )
        width = max(6, len(str(len(cards))))
        for index, card in enumerate(cards, start=1):
            source_id, content = card if isinstance(card, tuple) else (f"{deck_name}:{index}", card)
            encoded_cards.append(
                transit_map(
                    (
                        ("id", transit_keyword(stable_id("card", source_id))),
                        ("deck-id", transit_keyword(deck_id)),
                        ("content", transit_string(content)),
                        ("pos", f"{index:0{width}d}"),
                    )
                )
            )
    payload = transit_map((("version", 2), ("decks", encoded_decks), ("cards", encoded_cards)))
    _write_transit_archive(path, payload)


def decode_transit_map(value: object) -> dict[str, object]:
    """Decode an uncached Transit map emitted by this project."""
    if not isinstance(value, list) or not value or value[0] != "^ " or len(value) % 2 != 1:
        raise AssertionError("invalid Transit map")
    return {str(value[index])[2:]: value[index + 1] for index in range(1, len(value), 2)}


class _TransitReader:
    """Small Transit-JSON reader covering the native Mochi export structure."""

    def __init__(self) -> None:
        self.cache: list[str] = []

    @staticmethod
    def _cache_index(value: str) -> int:
        if len(value) == 2:
            return ord(value[1]) - 48
        return ord(value[2]) - 48 + 44 * (ord(value[1]) - 48)

    def read(self, value: object, *, map_key: bool = False) -> object:
        if isinstance(value, str):
            if value.startswith("^") and value != "^ ":
                value = self.cache[self._cache_index(value)]
                return self._scalar(value)
            if len(value) >= 4 and (map_key or value[:2] in {"~#", "~$", "~:"}):
                self.cache.append(value)
            return self._scalar(value)
        if isinstance(value, list):
            if value and value[0] == "^ ":
                return {
                    str(self.read(value[index], map_key=True)): self.read(value[index + 1])
                    for index in range(1, len(value), 2)
                }
            if len(value) == 2 and isinstance(value[0], str) and value[0].startswith("~#"):
                self.read(value[0])
                return self.read(value[1])
            return [self.read(item) for item in value]
        if isinstance(value, dict):
            return {str(self.read(key, map_key=True)): self.read(item) for key, item in value.items()}
        return value

    @staticmethod
    def _scalar(value: str) -> str:
        if value.startswith("~:") or value.startswith("~$"):
            return value[2:]
        if value.startswith(("~~", "~^", "~`")):
            return value[1:]
        return value


def read_mochi(path: Path) -> dict[str, object]:
    with zipfile.ZipFile(path) as archive:
        if "data.json" not in archive.namelist():
            raise ValueError(f"{path.name} has no Transit data.json")
        raw = json.loads(archive.read("data.json"))
    root = _TransitReader().read(raw)
    if not isinstance(root, dict) or root.get("version") != 2:
        raise ValueError(f"{path.name} is not a Mochi v2 archive")
    return root


def _deck_index(root: dict[str, object]) -> dict[str, dict[str, object]]:
    decks: dict[str, dict[str, object]] = {}
    by_id: dict[str, dict[str, object]] = {}
    for raw_deck in root.get("decks", []):
        deck = dict(raw_deck)
        deck.setdefault("cards", [])
        name = str(deck.get("name", ""))
        deck_id = str(deck.get("id", ""))
        decks[name] = deck
        if deck_id:
            by_id[deck_id] = deck
    for raw_card in root.get("cards", []):
        card = dict(raw_card)
        deck = by_id.get(str(card.get("deck-id", "")))
        if deck is not None:
            deck["cards"].append(card)
    return decks


def _front(content: str) -> str:
    return next((line[2:].strip() for line in content.splitlines() if line.startswith("# ")), "")


def prepare_mochi_update(existing: Path, release: Path, output: Path) -> dict[str, int]:
    """Create a native update package while retaining IDs in an imported deck."""
    current_decks = _deck_index(read_mochi(existing))
    release_decks = _deck_index(read_mochi(release))
    updates: list[list[object]] = []
    matched = added = retained = 0

    for name, new_deck in release_decks.items():
        if name not in current_decks:
            raise ValueError(f"existing export does not contain deck: {name}")
        current_deck = current_decks[name]
        current_deck_id = str(current_deck.get("id", ""))
        if not current_deck_id:
            raise ValueError(f"existing deck has no Mochi ID: {name}")
        current_cards = list(current_deck["cards"])
        by_id = {str(card.get("id")): card for card in current_cards if card.get("id")}
        by_pos = {str(card.get("pos")): card for card in current_cards if card.get("pos")}
        by_front: dict[str, list[dict[str, object]]] = defaultdict(list)
        for card in current_cards:
            by_front[_front(str(card.get("content", "")))].append(card)
        used: set[str] = set()

        for new_card in new_deck["cards"]:
            new_id = str(new_card.get("id", ""))
            pos = str(new_card.get("pos", ""))
            front = _front(str(new_card.get("content", "")))
            old = by_id.get(new_id)
            if old is None:
                candidate = by_pos.get(pos)
                old = candidate if candidate and _front(str(candidate.get("content", ""))) == front else None
            if old is None and len(by_front[front]) == 1:
                old = by_front[front][0]
            card_id = str(old.get("id")) if old else new_id
            if not card_id:
                raise ValueError(f"new card has no ID: {name}/{front}")
            used.add(card_id)
            matched += old is not None
            added += old is None
            updates.append(
                transit_map(
                    (
                        ("id", transit_keyword(card_id)),
                        ("deck-id", transit_keyword(current_deck_id)),
                        ("content", transit_string(str(new_card["content"]))),
                        ("pos", pos),
                    )
                )
            )
        retained += sum(str(card.get("id", "")) not in used for card in current_cards)

    _write_transit_archive(output, transit_map((("version", 2), ("cards", updates))))
    return {"updated": matched, "added": added, "retained": retained}


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
        vocabulary_deck = (
            f"JLPT {level} Vocabulary",
            [(record["id"], vocabulary_card(record)) for record in vocabulary],
        )
        kanji_deck = (
            f"JLPT {level} Kanji",
            [(record["id"], kanji_card(record)) for record in kanji],
        )
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
            root = read_mochi(artifact.path)
        except (OSError, zipfile.BadZipFile, json.JSONDecodeError, IndexError, ValueError) as exc:
            return [f"invalid Mochi archive {artifact.path.name}: {exc}"]
        decks = _deck_index(root)
        if len(decks) != len(artifact.decks):
            errors.append(f"wrong Mochi deck count: {artifact.path.name}")
            return errors
        all_ids: set[str] = set()
        for expected_name, expected_count in artifact.decks:
            deck = decks.get(expected_name)
            if deck is None or len(deck["cards"]) != expected_count:
                errors.append(f"wrong Mochi contents: {artifact.path.name}/{expected_name}")
                continue
            cards = deck["cards"]
            positions = [str(card.get("pos", "")) for card in cards]
            card_ids = [str(card.get("id", "")) for card in cards]
            if positions != sorted(positions) or len(positions) != len(set(positions)):
                errors.append(f"invalid Mochi positions: {artifact.path.name}/{expected_name}")
            if any(not value for value in card_ids) or any(value in all_ids for value in card_ids):
                errors.append(f"invalid Mochi card IDs: {artifact.path.name}/{expected_name}")
            all_ids.update(card_ids)
            if any(has_tag_like_markdown(str(card.get("content", ""))) for card in cards):
                errors.append(f"tag-like Markdown in Mochi cards: {artifact.path.name}/{expected_name}")
        return errors
