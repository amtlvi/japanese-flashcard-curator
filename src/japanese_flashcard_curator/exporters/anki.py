"""Dependency-free, deterministic Anki ``.apkg`` exporter.

The package uses Anki's legacy-compatible SQLite deck-package layout
(``collection.anki2`` plus ``media``). Current Anki versions continue to import
this format, and it avoids coupling the curator to Anki's application runtime.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sqlite3
import tempfile
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .base import DeckArtifact, Record


PACKAGE_EPOCH = 1_700_000_000
FIELD_SEPARATOR = "\x1f"
RUBY_RE = re.compile(r"\{([^{}]+)\}\(([^()]*)\)")

SCHEMA = """
CREATE TABLE col (
  id integer primary key, crt integer not null, mod integer not null,
  scm integer not null, ver integer not null, dty integer not null,
  usn integer not null, ls integer not null, conf text not null,
  models text not null, decks text not null, dconf text not null,
  tags text not null
);
CREATE TABLE notes (
  id integer primary key, guid text not null, mid integer not null,
  mod integer not null, usn integer not null, tags text not null,
  flds text not null, sfld integer not null, csum integer not null,
  flags integer not null, data text not null
);
CREATE TABLE cards (
  id integer primary key, nid integer not null, did integer not null,
  ord integer not null, mod integer not null, usn integer not null,
  type integer not null, queue integer not null, due integer not null,
  ivl integer not null, factor integer not null, reps integer not null,
  lapses integer not null, left integer not null, odue integer not null,
  odid integer not null, flags integer not null, data text not null
);
CREATE TABLE revlog (
  id integer primary key, cid integer not null, usn integer not null,
  ease integer not null, ivl integer not null, lastIvl integer not null,
  factor integer not null, time integer not null, type integer not null
);
CREATE TABLE graves (usn integer not null, oid integer not null, type integer not null);
CREATE INDEX ix_notes_usn ON notes (usn);
CREATE INDEX ix_cards_usn ON cards (usn);
CREATE INDEX ix_revlog_usn ON revlog (usn);
CREATE INDEX ix_cards_nid ON cards (nid);
CREATE INDEX ix_cards_sched ON cards (did, queue, due);
CREATE INDEX ix_revlog_cid ON revlog (cid);
CREATE INDEX ix_notes_csum ON notes (csum);
"""

DEFAULT_DECK_CONFIG = {
    "1": {
        "autoplay": True,
        "id": 1,
        "lapse": {"delays": [10], "leechAction": 0, "leechFails": 8, "minInt": 1, "mult": 0},
        "maxTaken": 60,
        "mod": 0,
        "name": "Default",
        "new": {
            "bury": True,
            "delays": [1, 10],
            "initialFactor": 2500,
            "ints": [1, 4, 7],
            "order": 1,
            "perDay": 20,
            "separate": True,
        },
        "replayq": True,
        "rev": {
            "bury": True,
            "ease4": 1.3,
            "fuzz": 0.05,
            "ivlFct": 1,
            "maxIvl": 36500,
            "minSpace": 1,
            "perDay": 100,
        },
        "timer": 0,
        "usn": 0,
    }
}

DEFAULT_DECK = {
    "collapsed": False,
    "conf": 1,
    "desc": "",
    "dyn": 0,
    "extendNew": 0,
    "extendRev": 50,
    "id": 1,
    "lrnToday": [0, 0],
    "mod": PACKAGE_EPOCH,
    "name": "Default",
    "newToday": [0, 0],
    "revToday": [0, 0],
    "timeToday": [0, 0],
    "usn": 0,
}

CARD_CSS = """
.card { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: 20px; text-align: left; color: #222; background: #fff; max-width: 46rem; margin: auto; }
.front { font-size: 2.2rem; text-align: center; margin: 1rem 0; }
.answer { line-height: 1.5; }
.headword { font-size: 1.8rem; text-align: center; }
.reading, .meta { color: #666; text-align: center; }
.label { color: #666; font-size: .8rem; font-weight: 600; letter-spacing: .04em; margin-top: 1rem; text-transform: uppercase; }
.example { border-left: 3px solid #ddd; margin: .7rem 0; padding-left: .8rem; }
.english { color: #555; font-style: italic; }
.copyable { background: #f5f5f5; border-radius: .35rem; overflow-wrap: anywhere; padding: .7rem; white-space: pre-wrap; }
ul { margin-top: .3rem; }
rt { font-size: .55em; }
.nightMode .card { color: #eee; background: #222; }
.nightMode .reading, .nightMode .meta, .nightMode .label, .nightMode .english { color: #bbb; }
.nightMode .copyable { background: #333; }
""".strip()


@dataclass(frozen=True)
class AnkiDeck:
    level: str
    kind: str
    name: str
    records: Sequence[Record]

    @property
    def deck_id(self) -> int:
        return stable_int(f"deck:{self.level}:{self.kind}", 1 << 30, 1 << 30)


def stable_int(value: str, lower: int, span: int) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return lower + int.from_bytes(digest[:8], "big") % span


def stable_guid(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


def field_checksum(value: str) -> int:
    return int(hashlib.sha1(value.encode("utf-8")).hexdigest()[:8], 16)


def compact_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def mochi_furigana_to_html(markup: str, surface: str, reading: str) -> str:
    """Convert canonical Mochi ruby markup to portable HTML for Anki cards."""
    if markup.startswith("<furigana>") and markup.endswith("</furigana>"):
        if surface == reading or not reading:
            return html.escape(surface)
        return f"<ruby>{html.escape(surface)}<rt>{html.escape(reading)}</rt></ruby>"
    out: list[str] = []
    cursor = 0
    for match in RUBY_RE.finditer(markup):
        out.append(html.escape(markup[cursor : match.start()]))
        out.append(f"<ruby>{html.escape(match.group(1))}<rt>{html.escape(match.group(2))}</rt></ruby>")
        cursor = match.end()
    out.append(html.escape(markup[cursor:]))
    return "".join(out)


def html_list(values: Sequence[str]) -> str:
    return "<ul>" + "".join(f"<li>{html.escape(value)}</li>" for value in values) + "</ul>"


def clean_copy_values(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(" ".join(value.split()) for value in values if value.strip()))


def vocabulary_fields(record: Record) -> list[str]:
    examples = "".join(
        "<div class=\"example\">"
        f"<div lang=\"ja\">{html.escape(example['japanese_raw'])}</div>"
        f"<div class=\"english\">{html.escape(example['english'])}</div>"
        "</div>"
        for example in record["examples"]
    )
    copy_values = clean_copy_values([example["japanese_raw"] for example in record["examples"]])
    if not copy_values:
        copy_values = [record["written"]["lookup_text"]]
    meanings = html_list(record["meanings"])
    if record["kanji_details"]:
        meanings += '<div class="label">Kanji in this word</div>' + html_list(
            [f"{detail['character']} — {'; '.join(detail['meanings'])}" for detail in record["kanji_details"]]
        )
    return [
        html.escape(record["id"]),
        html.escape(record["written"]["without_furigana"]),
        mochi_furigana_to_html(
            record["written"]["with_furigana"],
            record["written"]["without_furigana"],
            record["reading"]["primary"],
        ),
        html.escape(record["reading"]["primary"]),
        meanings,
        html.escape("; ".join(part["label"] for part in record["parts_of_speech"])),
        examples,
        html.escape("\n".join(copy_values)),
        html.escape(
            f"JLPT {record['level']} · order {record['order']} · "
            f"JMdict {record['provenance']['dictionary_entry_id'] or 'unmatched'}"
        ),
    ]


def kanji_fields(record: Record) -> list[str]:
    components = "、".join(
        html.escape(component["symbol"])
        + (f" ({html.escape(', '.join(component['meanings']))})" if component["meanings"] else "")
        for component in record["components"]
    ) or "Atomic in KRADFILE"
    example_words = "".join(
        "<div class=\"example\">"
        f"<span lang=\"ja\">{mochi_furigana_to_html(word['written_furigana'], word['written_raw'], word['reading'])}</span>"
        f" — {html.escape('; '.join(word['meanings']))}"
        "</div>"
        for word in record["example_words"]
    )
    copy_values = clean_copy_values([record["character"], *(word["written_raw"] for word in record["example_words"])])
    stats = [f"{record['strokes']} strokes"]
    if record["grade"] is not None:
        stats.append(f"grade {record['grade']}")
    if record["frequency_rank"] is not None:
        stats.append(f"frequency #{record['frequency_rank']}")
    return [
        html.escape(record["id"]),
        html.escape(record["character"]),
        html_list(record["meanings"]),
        html.escape("、".join(record["readings"]["onyomi"])),
        html.escape("、".join(record["readings"]["kunyomi"])),
        components,
        example_words,
        html.escape("\n".join(copy_values)),
        html.escape(f"JLPT {record['level']} · order {record['order']} · {' · '.join(stats)}"),
    ]


def note_model(kind: str, deck_id: int) -> dict[str, Any]:
    model_id = stable_int(f"model:{kind}:v1", 1 << 30, 1 << 30)
    if kind == "vocabulary":
        fields = ["ID", "Expression", "Furigana", "Reading", "Meanings", "Part of Speech", "Examples", "Copyable Japanese", "Source"]
        front = '<div class="front" lang="ja">{{Expression}}</div>'
        back = """{{FrontSide}}<hr id="answer"><div class="answer">
<div class="headword" lang="ja">{{Furigana}}</div><div class="reading">{{Reading}}</div>
<div class="label">Meanings</div>{{Meanings}}
{{#Part of Speech}}<div class="label">Part of speech</div><div>{{Part of Speech}}</div>{{/Part of Speech}}
{{#Examples}}<div class="label">Examples</div>{{Examples}}{{/Examples}}
<div class="label">Copyable Japanese</div><pre class="copyable" lang="ja">{{Copyable Japanese}}</pre>
<div class="meta">{{Source}}</div></div>"""
        name = "Japanese Flashcard Curator Vocabulary"
    else:
        fields = ["ID", "Character", "Meanings", "Onyomi", "Kunyomi", "Components", "Example Words", "Copyable Japanese", "Source"]
        front = '<div class="front" lang="ja">{{Character}}</div>'
        back = """{{FrontSide}}<hr id="answer"><div class="answer">
<div class="label">Meanings</div>{{Meanings}}
{{#Onyomi}}<div class="label">On’yomi</div><div lang="ja">{{Onyomi}}</div>{{/Onyomi}}
{{#Kunyomi}}<div class="label">Kun’yomi</div><div lang="ja">{{Kunyomi}}</div>{{/Kunyomi}}
<div class="label">Visible components (KRADFILE)</div><div lang="ja">{{Components}}</div>
{{#Example Words}}<div class="label">Example words</div>{{Example Words}}{{/Example Words}}
<div class="label">Copyable Japanese</div><pre class="copyable" lang="ja">{{Copyable Japanese}}</pre>
<div class="meta">{{Source}}</div></div>"""
        name = "Japanese Flashcard Curator Kanji"
    field_defs = [
        {"font": "Arial", "media": [], "name": field, "ord": index, "rtl": False, "size": 20, "sticky": False}
        for index, field in enumerate(fields)
    ]
    template = {
        "afmt": back,
        "bafmt": "",
        "bfont": "",
        "bqfmt": "",
        "bsize": 0,
        "did": None,
        "name": "Recognition",
        "ord": 0,
        "qfmt": front,
    }
    return {
        "css": CARD_CSS,
        "did": deck_id,
        "flds": field_defs,
        "id": str(model_id),
        "latexPost": "\\end{document}",
        "latexPre": "\\documentclass[12pt]{article}\\begin{document}",
        "latexsvg": False,
        "mod": PACKAGE_EPOCH,
        "name": name,
        "req": [[0, "all", [1]]],
        "sortf": 1,
        "tags": [],
        "tmpls": [template],
        "type": 0,
        "usn": -1,
        "vers": [],
    }


def deck_json(deck: AnkiDeck) -> dict[str, Any]:
    return {
        "collapsed": False,
        "conf": 1,
        "desc": "Generated by Japanese Flashcard Curator",
        "dyn": 0,
        "extendNew": 0,
        "extendRev": 50,
        "id": deck.deck_id,
        "lrnToday": [0, 0],
        "mod": PACKAGE_EPOCH,
        "name": deck.name,
        "newToday": [0, 0],
        "revToday": [0, 0],
        "timeToday": [0, 0],
        "usn": -1,
    }


def write_collection(path: Path, decks: Sequence[AnkiDeck]) -> None:
    models = {str(stable_int(f"model:{deck.kind}:v1", 1 << 30, 1 << 30)): note_model(deck.kind, deck.deck_id) for deck in decks}
    deck_map = {"1": DEFAULT_DECK, **{str(deck.deck_id): deck_json(deck) for deck in decks}}
    active_decks = [deck.deck_id for deck in decks]
    config = {
        "activeDecks": active_decks,
        "addToCur": True,
        "collapseTime": 1200,
        "curDeck": active_decks[0],
        "curModel": next(iter(models)),
        "dueCounts": True,
        "estTimes": True,
        "newBury": True,
        "newSpread": 0,
        "nextPos": 1 + sum(len(deck.records) for deck in decks),
        "sortBackwards": False,
        "sortType": "noteFld",
        "timeLim": 0,
    }
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA journal_mode=OFF")
        connection.execute("PRAGMA synchronous=OFF")
        connection.execute("PRAGMA page_size=4096")
        connection.executescript(SCHEMA)
        connection.execute(
            "INSERT INTO col VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                1,
                PACKAGE_EPOCH,
                PACKAGE_EPOCH * 1000,
                PACKAGE_EPOCH * 1000,
                11,
                0,
                0,
                0,
                compact_json(config),
                compact_json(models),
                compact_json(deck_map),
                compact_json(DEFAULT_DECK_CONFIG),
                "{}",
            ),
        )
        seen_ids: set[int] = set()
        for deck in decks:
            model_id = stable_int(f"model:{deck.kind}:v1", 1 << 30, 1 << 30)
            for record in deck.records:
                fields = vocabulary_fields(record) if deck.kind == "vocabulary" else kanji_fields(record)
                note_id = stable_int(f"note:{record['id']}", 1_000_000_000_000, 8_000_000_000_000)
                card_id = stable_int(f"card:{record['id']}", 1_000_000_000_000, 8_000_000_000_000)
                if note_id in seen_ids or card_id in seen_ids:
                    raise RuntimeError(f"Anki ID collision for {record['id']}")
                seen_ids.update((note_id, card_id))
                connection.execute(
                    "INSERT INTO notes VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        note_id,
                        stable_guid(f"note:{record['id']}"),
                        model_id,
                        PACKAGE_EPOCH,
                        -1,
                        f" JLPT::{record['level']} JFC {deck.kind} ",
                        FIELD_SEPARATOR.join(fields),
                        fields[1],
                        field_checksum(fields[0]),
                        0,
                        "",
                    ),
                )
                connection.execute(
                    "INSERT INTO cards VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        card_id,
                        note_id,
                        deck.deck_id,
                        0,
                        PACKAGE_EPOCH,
                        -1,
                        0,
                        0,
                        record["order"],
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                        "",
                    ),
                )
        connection.commit()
        connection.execute("VACUUM")
    finally:
        connection.close()


def write_anki_package(path: Path, decks: Sequence[AnkiDeck]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, database_name = tempfile.mkstemp(prefix="jfc-anki-", suffix=".anki2")
    os.close(descriptor)
    database_path = Path(database_name)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        write_collection(database_path, decks)
        database = database_path.read_bytes()
        with zipfile.ZipFile(temporary, "w") as archive:
            for name, data in (("collection.anki2", database), ("media", b"{}")):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o600 << 16
                archive.writestr(info, data)
        temporary.replace(path)
    finally:
        database_path.unlink(missing_ok=True)
        temporary.unlink(missing_ok=True)


def validate_anki_package(artifact: DeckArtifact) -> list[str]:
    errors: list[str] = []
    descriptor, database_name = tempfile.mkstemp(prefix="jfc-validate-", suffix=".anki2")
    os.close(descriptor)
    database_path = Path(database_name)
    try:
        try:
            with zipfile.ZipFile(artifact.path) as archive:
                if archive.namelist() != ["collection.anki2", "media"] or archive.testzip() is not None:
                    return [f"invalid Anki archive: {artifact.path.name}"]
                if json.loads(archive.read("media")) != {}:
                    errors.append(f"unexpected Anki media map: {artifact.path.name}")
                database_path.write_bytes(archive.read("collection.anki2"))
        except (OSError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
            return [f"invalid Anki archive {artifact.path.name}: {exc}"]
        connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
        try:
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                errors.append(f"Anki SQLite integrity failed: {artifact.path.name}")
            note_count = connection.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
            card_count = connection.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
            guid_count = connection.execute("SELECT COUNT(DISTINCT guid) FROM notes").fetchone()[0]
            if note_count != artifact.card_count or card_count != artifact.card_count or guid_count != artifact.card_count:
                errors.append(f"wrong Anki note/card count: {artifact.path.name}")
            decks = json.loads(connection.execute("SELECT decks FROM col").fetchone()[0])
            for expected_name, expected_count in artifact.decks:
                matching_ids = [int(deck_id) for deck_id, value in decks.items() if value["name"] == expected_name]
                if len(matching_ids) != 1:
                    errors.append(f"missing Anki deck: {artifact.path.name}/{expected_name}")
                    continue
                rows = connection.execute(
                    "SELECT due, type, queue, ivl, reps FROM cards WHERE did=? ORDER BY due",
                    (matching_ids[0],),
                ).fetchall()
                if len(rows) != expected_count or [row[0] for row in rows] != list(range(1, expected_count + 1)):
                    errors.append(f"wrong Anki card order: {artifact.path.name}/{expected_name}")
                if any(row[1:] != (0, 0, 0, 0) for row in rows):
                    errors.append(f"Anki scheduling state leaked: {artifact.path.name}/{expected_name}")
            if connection.execute("SELECT COUNT(*) FROM notes WHERE flds LIKE '%<furigana>%' OR flds LIKE '%{%}(%'").fetchone()[0]:
                errors.append(f"Mochi markup leaked into Anki fields: {artifact.path.name}")
        finally:
            connection.close()
    finally:
        database_path.unlink(missing_ok=True)
    return errors


class AnkiExporter:
    name = "anki"
    extension = ".apkg"

    def export(
        self,
        level: str,
        vocabulary: Sequence[Record],
        kanji: Sequence[Record],
        output_dir: Path,
    ) -> list[DeckArtifact]:
        vocabulary_deck = AnkiDeck(level, "vocabulary", f"JLPT {level} Vocabulary", vocabulary)
        kanji_deck = AnkiDeck(level, "kanji", f"JLPT {level} Kanji", kanji)
        stem = f"jlpt_{level.lower()}"
        specs = (
            ("vocabulary", output_dir / f"{stem}_vocabulary.apkg", (vocabulary_deck,)),
            ("kanji", output_dir / f"{stem}_kanji.apkg", (kanji_deck,)),
            ("complete", output_dir / f"{stem}_complete.apkg", (vocabulary_deck, kanji_deck)),
        )
        artifacts = []
        for scope, path, decks in specs:
            write_anki_package(path, decks)
            artifacts.append(
                DeckArtifact(
                    format=self.name,
                    scope=scope,
                    path=path,
                    decks=tuple((deck.name, len(deck.records)) for deck in decks),
                )
            )
        return artifacts

    def validate(self, artifact: DeckArtifact) -> list[str]:
        return validate_anki_package(artifact)
