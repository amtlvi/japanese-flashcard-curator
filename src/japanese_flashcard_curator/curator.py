#!/usr/bin/env python3
"""Reproducibly curate JLPT data and export deterministic flashcard decks."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import shutil
import urllib.request
import zipfile
from collections import defaultdict
from importlib import resources
from pathlib import Path
from typing import Any, Sequence

from .exporters import (
    DeckArtifact,
    get_exporter,
    select_exporters,
)


WORKSPACE = Path.cwd()
CACHE = WORKSPACE / ".cache"
GENERATED = WORKSPACE / "data" / "generated"
DIST = WORKSPACE / "dist"
RELEASE = WORKSPACE / "release-artifacts"
PACKAGE_DATA = resources.files("japanese_flashcard_curator") / "data"
LEVELS = ("N5", "N4", "N3", "N2", "N1")
KANJI_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff々〆ヶ]")
VARIANT_SPLIT_RE = re.compile(r"\s*[;；]\s*")
TAG_LESSON_RE = re.compile(r"Genki_Ln\.(\d+)")
SOURCE_REPOS = {
    "vocabulary": "https://raw.githubusercontent.com/{repository}/{commit}/{path}",
    "kanji": "https://raw.githubusercontent.com/{repository}/{commit}/{path}",
}
RELEASE_BASE = "https://github.com/scriptin/jmdict-simplified/releases/download/{tag}/{file}"


def json_dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_lock() -> dict[str, Any]:
    return json.loads((PACKAGE_DATA / "sources.lock.json").read_text(encoding="utf-8"))


def load_overrides() -> dict[str, Any]:
    return json.loads((PACKAGE_DATA / "overrides.json").read_text(encoding="utf-8"))


def verified_download(url: str, destination: Path, expected_sha256: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and sha256(destination) == expected_sha256:
        return
    temporary = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "japanese-flashcard-curator"})
    with urllib.request.urlopen(request, timeout=300) as response, temporary.open("wb") as output:
        shutil.copyfileobj(response, output)
    actual = sha256(temporary)
    if actual != expected_sha256:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"Checksum mismatch for {url}: expected {expected_sha256}, got {actual}")
    temporary.replace(destination)


def fetch(levels: Sequence[str]) -> None:
    lock = load_lock()
    for kind, source in lock["level_maps"].items():
        for level in levels:
            item = source["files"][level]
            url = SOURCE_REPOS[kind].format(
                repository=source["repository"], commit=source["commit"], path=item["path"]
            )
            verified_download(url, CACHE / kind / f"{level.lower()}.csv", item["sha256"])
    release = lock["dictionary_release"]
    for key, asset in release["assets"].items():
        url = RELEASE_BASE.format(tag=release["tag"].replace("+", "%2B"), file=asset["file"])
        verified_download(url, CACHE / "dictionary" / f"{key}.zip", asset["sha256"])


def read_zip_json(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.endswith(".json")]
        if len(members) != 1:
            raise RuntimeError(f"Expected one JSON member in {path}, found {members}")
        with archive.open(members[0]) as handle:
            return json.load(io.TextIOWrapper(handle, encoding="utf-8"))


def split_variants(value: str) -> list[str]:
    return [part.strip().replace("～", "〜") for part in VARIANT_SPLIT_RE.split(value) if part.strip()]


def strip_affix_marker(value: str) -> str:
    return value.replace("〜", "").strip()


def katakana_to_hiragana(value: str) -> str:
    out = []
    for char in value:
        code = ord(char)
        out.append(chr(code - 0x60) if 0x30A1 <= code <= 0x30F6 else char)
    return "".join(out)


def normalize_reading(value: str) -> str:
    return katakana_to_hiragana(strip_affix_marker(value)).replace(" ", "")


def clean_source_reading(value: str) -> str:
    """Remove source-list grammar hints that are not part of a dictionary reading."""
    value = re.sub(r"^\(〜を\)\s*", "", value.strip())
    value = re.sub(r"\s*\(する\)$", "", value)
    return value.strip()


def has_kanji(value: str) -> bool:
    return bool(KANJI_RE.search(value))


def split_kanji_runs(value: str) -> list[tuple[bool, str]]:
    if not value:
        return []
    runs: list[tuple[bool, str]] = []
    current_kind = has_kanji(value[0])
    current = [value[0]]
    for char in value[1:]:
        kind = has_kanji(char)
        if kind == current_kind:
            current.append(char)
        else:
            runs.append((current_kind, "".join(current)))
            current_kind, current = kind, [char]
    runs.append((current_kind, "".join(current)))
    return runs


def explicit_furigana(surface: str, reading: str) -> str:
    """Return Mochi explicit ruby markup, falling back to automatic furigana."""
    if not surface or not has_kanji(surface):
        return surface
    normalized = normalize_reading(reading)
    if not normalized:
        return f"<furigana>{surface}</furigana>"
    prefix = "〜" if surface.startswith("〜") else ""
    suffix = "〜" if surface.endswith("〜") else ""
    core = strip_affix_marker(surface)
    runs = split_kanji_runs(core)
    cursor = 0
    output: list[str] = []
    for index, (is_kanji, text) in enumerate(runs):
        if not is_kanji:
            anchor = normalize_reading(text)
            if normalized[cursor : cursor + len(anchor)] != anchor:
                return f"<furigana>{surface}</furigana>"
            output.append(text)
            cursor += len(anchor)
            continue
        if index + 1 < len(runs):
            anchor = normalize_reading(runs[index + 1][1])
            boundary = normalized.find(anchor, cursor + 1)
            if boundary < 0:
                return f"<furigana>{surface}</furigana>"
        else:
            boundary = len(normalized)
        ruby = normalized[cursor:boundary]
        if not ruby:
            return f"<furigana>{surface}</furigana>"
        output.append(f"{{{text}}}({ruby})")
        cursor = boundary
    if cursor != len(normalized):
        return f"<furigana>{surface}</furigana>"
    return prefix + "".join(output) + suffix


def source_rows(level: str) -> list[dict[str, str]]:
    with (CACHE / "vocabulary" / f"{level.lower()}.csv").open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def source_kanji(level: str) -> list[str]:
    with (CACHE / "kanji" / f"{level.lower()}.csv").open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return [row[reader.fieldnames[0]].strip() for row in reader if row[reader.fieldnames[0]].strip()]


def forms_for_row(row: dict[str, str]) -> tuple[list[str], list[str]]:
    written = split_variants(row["expression"])
    readings = [clean_source_reading(value) for value in split_variants(row["reading"])]
    readings = [value for value in readings if value]
    return written, readings or [strip_affix_marker(written[0])]


def jmdict_candidates(words: list[dict[str, Any]], needed_forms: set[str]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in words:
        forms = {item["text"] for item in entry.get("kanji", []) + entry.get("kana", [])}
        for form in forms & needed_forms:
            result[form].append(entry)
    return result


def entry_readings(entry: dict[str, Any]) -> set[str]:
    return {normalize_reading(item["text"]) for item in entry.get("kana", [])}


def entry_common(entry: dict[str, Any]) -> bool:
    return any(item.get("common") for item in entry.get("kanji", []) + entry.get("kana", []))


def match_entry(
    written: Sequence[str], readings: Sequence[str], candidates: dict[str, list[dict[str, Any]]]
) -> dict[str, Any] | None:
    normalized_readings = {normalize_reading(x) for x in readings if normalize_reading(x)}
    options: dict[str, dict[str, Any]] = {}
    for form in written:
        for candidate in candidates.get(strip_affix_marker(form), []):
            options[candidate["id"]] = candidate
    if not options:
        for reading in readings:
            for candidate in candidates.get(strip_affix_marker(reading), []):
                options[candidate["id"]] = candidate
    if not options:
        return None
    ranked = sorted(
        options.values(),
        key=lambda entry: (
            0 if normalized_readings & entry_readings(entry) else 1,
            0 if entry_common(entry) else 1,
            int(entry["id"]),
        ),
    )
    return ranked[0]


def relevant_senses(entry: dict[str, Any], written: Sequence[str], readings: Sequence[str]) -> list[dict[str, Any]]:
    forms = {strip_affix_marker(x) for x in written}
    kana = {strip_affix_marker(x) for x in readings}
    relevant = []
    for sense in entry.get("sense", []):
        applies_k = set(sense.get("appliesToKanji", ["*"]))
        applies_r = set(sense.get("appliesToKana", ["*"]))
        if ("*" in applies_k or forms & applies_k) and ("*" in applies_r or kana & applies_r):
            relevant.append(sense)
    return relevant or entry.get("sense", [])


def sense_examples(senses: Sequence[dict[str, Any]], limit: int = 2) -> list[dict[str, str]]:
    examples: list[dict[str, str]] = []
    seen: set[str] = set()
    for sense in senses:
        for example in sense.get("examples", []):
            ja = next((s["text"] for s in example.get("sentences", []) if s.get("lang") == "jpn"), "")
            en = next((s["text"] for s in example.get("sentences", []) if s.get("lang") == "eng"), "")
            if not ja or not en or ja in seen:
                continue
            seen.add(ja)
            examples.append(
                {
                    "japanese_raw": ja,
                    "japanese_furigana": f"<furigana>{ja}</furigana>",
                    "english": en,
                    "source": example.get("source", {}).get("type", "tatoeba"),
                    "source_id": str(example.get("source", {}).get("value", "")),
                }
            )
    examples.sort(key=lambda example: (len(example["japanese_raw"]), example["japanese_raw"]))
    return examples[:limit]


def parse_meanings(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"\s*;\s*|,\s+(?=[a-zA-Z(])", value) if part.strip()]


def vocabulary_records(level: str, jmdict: dict[str, Any]) -> list[dict[str, Any]]:
    rows = source_rows(level)
    aliases = load_overrides().get("vocabulary_aliases", {})
    example_suppressions = set(load_overrides().get("example_suppressions", []))
    needed: set[str] = set()
    parsed: list[tuple[list[str], list[str], list[str]]] = []
    for row in rows:
        written, readings = forms_for_row(row)
        lookup_aliases = aliases.get(written[0], [])
        parsed.append((written, readings, lookup_aliases))
        needed.update(strip_affix_marker(x) for x in written + readings + lookup_aliases)
    candidates = jmdict_candidates(jmdict["words"], needed)
    tags = jmdict.get("tags", {})
    temporary = []
    for source_index, (row, (written, readings, lookup_aliases)) in enumerate(zip(rows, parsed), start=1):
        lookup_written = [*written, *lookup_aliases]
        entry = match_entry(lookup_written, readings, candidates)
        senses = relevant_senses(entry, lookup_written, readings) if entry else []
        pos_codes = list(dict.fromkeys(code for sense in senses for code in sense.get("partOfSpeech", [])))
        lessons = [int(x) for x in TAG_LESSON_RE.findall(row.get("tags", ""))]
        common = entry_common(entry) if entry else False
        primary_reading = readings[0]
        primary_written = written[0]
        record = {
            "id": "",
            "level": level,
            "order": 0,
            "source_order": source_index,
            "curriculum": {"genki_lesson": min(lessons) if lessons else None},
            "written": {
                "primary": primary_written,
                "variants": written,
                "without_furigana": primary_written,
                "with_furigana": explicit_furigana(primary_written, primary_reading),
                "lookup_text": strip_affix_marker(primary_written),
            },
            "reading": {
                "primary": primary_reading,
                "variants": readings,
                "source_text": row["reading"],
            },
            "meanings": parse_meanings(row["meaning"]),
            "parts_of_speech": [{"code": code, "label": tags.get(code, code)} for code in pos_codes],
            "common": common,
            "examples": [] if primary_written in example_suppressions else sense_examples(senses),
            "provenance": {
                "level_map": "open-anki-jlpt-decks",
                "level_map_guid": row.get("guid", ""),
                "dictionary": "JMdict",
                "dictionary_entry_id": entry["id"] if entry else None,
                "dictionary_lookup_aliases": lookup_aliases,
                "examples": "JMdict sense-linked Tatoeba examples" if entry else None,
            },
        }
        group = 0 if lessons else (1 if common else 2)
        temporary.append(((group, min(lessons) if lessons else 999, source_index), record))
    temporary.sort(key=lambda item: item[0])
    records = []
    for order, (_, record) in enumerate(temporary, start=1):
        record["order"] = order
        record["id"] = f"{level.lower()}-vocab-{order:04d}"
        records.append(record)
    return records


def kanjidic_index(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["literal"]: item for item in data["characters"]}


def kanji_meanings(entry: dict[str, Any] | None) -> list[str]:
    if not entry:
        return []
    return list(
        dict.fromkeys(
            meaning["value"]
            for group in entry.get("readingMeaning", {}).get("groups", [])
            for meaning in group.get("meanings", [])
            if meaning.get("lang") == "en"
        )
    )


def kanji_readings(entry: dict[str, Any] | None, reading_type: str) -> list[str]:
    if not entry:
        return []
    return list(
        dict.fromkeys(
            reading["value"]
            for group in entry.get("readingMeaning", {}).get("groups", [])
            for reading in group.get("readings", [])
            if reading.get("type") == reading_type
        )
    )


def kanji_records(
    level: str,
    characters: Sequence[str],
    kdic: dict[str, dict[str, Any]],
    krad: dict[str, list[str]],
    vocabulary: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    records = []
    for source_index, character in enumerate(characters, start=1):
        entry = kdic.get(character)
        misc = entry.get("misc", {}) if entry else {}
        components = [symbol for symbol in krad.get(character, []) if symbol != character]
        examples = []
        for word in vocabulary:
            if any(character in variant for variant in word["written"]["variants"]):
                examples.append(
                    {
                        "written_raw": word["written"]["primary"],
                        "written_furigana": word["written"]["with_furigana"],
                        "reading": word["reading"]["primary"],
                        "meanings": word["meanings"],
                    }
                )
            if len(examples) == 5:
                break
        component_records = [
            {"symbol": symbol, "meanings": kanji_meanings(kdic.get(symbol))[:3]}
            for symbol in components
        ]
        classical = [r["value"] for r in (entry.get("radicals", []) if entry else []) if r["type"] == "classical"]
        records.append(
            {
                "id": "",
                "level": level,
                "order": 0,
                "source_order": source_index,
                "character": character,
                "meanings": kanji_meanings(entry),
                "readings": {
                    "onyomi": kanji_readings(entry, "ja_on"),
                    "kunyomi": kanji_readings(entry, "ja_kun"),
                    "nanori": entry.get("readingMeaning", {}).get("nanori", []) if entry else [],
                },
                "strokes": (misc.get("strokeCounts") or [None])[0],
                "grade": misc.get("grade"),
                "frequency_rank": misc.get("frequency"),
                "classical_radical_numbers": classical,
                "radical_names": misc.get("radicalNames", []),
                "components": component_records,
                "atomic_component": not component_records,
                "example_words": examples,
                "provenance": {
                    "level_map": "Bluskyo/JLPT_Vocabulary (Jonathan Waller/Tanos)",
                    "dictionary": "KANJIDIC2",
                    "components": "KRADFILE visible components",
                },
            }
        )
    records.sort(key=lambda row: (row["frequency_rank"] is None, row["frequency_rank"] or 10**9, row["source_order"]))
    for order, record in enumerate(records, start=1):
        record["order"] = order
        record["id"] = f"{level.lower()}-kanji-{order:04d}"
    return records


def write_data_archive(path: Path, level: str) -> None:
    """Package canonical per-level data with stable names, metadata, and ordering."""
    level_dir = GENERATED / level.lower()
    members = ("vocabulary.json", "vocabulary.csv", "kanji.json", "kanji.csv", "report.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with zipfile.ZipFile(temporary, "w") as archive:
        for name in members:
            info = zipfile.ZipInfo(f"{level.lower()}/{name}", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, (level_dir / name).read_bytes())
    temporary.replace(path)


def package_release(levels: Sequence[str], formats: Sequence[str] = ()) -> list[Path]:
    RELEASE.mkdir(parents=True, exist_ok=True)
    for existing in RELEASE.iterdir():
        if existing.is_file():
            existing.unlink()
    artifacts: list[Path] = []
    for level in levels:
        report = verify(level, formats)
        selected = set(formats)
        for output in report["outputs"]:
            if selected and output["format"] not in selected:
                continue
            source = DIST / output["file"]
            destination = RELEASE / source.name
            shutil.copyfile(source, destination)
            artifacts.append(destination)
        stem = f"jlpt_{level.lower()}"
        data_archive = RELEASE / f"{stem}_data.zip"
        write_data_archive(data_archive, level)
        artifacts.append(data_archive)
    artifacts.sort(key=lambda item: item.name)
    checksums = "".join(f"{sha256(path)}  {path.name}\n" for path in artifacts)
    checksum_path = RELEASE / "SHA256SUMS"
    checksum_path.write_text(checksums, encoding="utf-8")
    return [checksum_path, *artifacts]


def write_csv(path: Path, rows: Sequence[dict[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] if isinstance(row[key], (str, int, float)) or row[key] is None else json.dumps(row[key], ensure_ascii=False) for key in fields})


def validate(
    level: str,
    vocab: Sequence[dict[str, Any]],
    kanji: Sequence[dict[str, Any]],
    artifacts: Sequence[DeckArtifact],
) -> dict[str, Any]:
    errors: list[str] = []
    lock = load_lock()
    expected_vocab = lock["level_maps"]["vocabulary"]["files"][level]["rows"]
    expected_kanji = lock["level_maps"]["kanji"]["files"][level]["rows"]
    if len(vocab) != expected_vocab: errors.append(f"expected {expected_vocab} vocabulary records, got {len(vocab)}")
    if len(kanji) != expected_kanji: errors.append(f"expected {expected_kanji} kanji records, got {len(kanji)}")
    if len({r["id"] for r in vocab}) != len(vocab): errors.append("duplicate vocabulary ids")
    if len({r["character"] for r in kanji}) != len(kanji): errors.append("duplicate kanji")
    if [r["order"] for r in vocab] != list(range(1, len(vocab) + 1)): errors.append("vocabulary order gap")
    if [r["order"] for r in kanji] != list(range(1, len(kanji) + 1)): errors.append("kanji order gap")
    if any("<furigana>" in e["japanese_raw"] or "{" in e["japanese_raw"] for r in vocab for e in r["examples"]): errors.append("markup leaked into raw examples")
    if len({artifact.path.name for artifact in artifacts}) != len(artifacts):
        errors.append("duplicate output filenames")
    for artifact in artifacts:
        errors.extend(get_exporter(artifact.format).validate(artifact))
    if errors:
        raise RuntimeError("Validation failed:\n- " + "\n- ".join(errors))
    coverage = sum(bool(r["examples"]) for r in vocab)
    matched = sum(r["provenance"]["dictionary_entry_id"] is not None for r in vocab)
    return {
        "level": level,
        "vocabulary_cards": len(vocab),
        "kanji_cards": len(kanji),
        "dictionary_matches": matched,
        "dictionary_match_percent": round(matched * 100 / len(vocab), 1),
        "cards_with_examples": coverage,
        "example_coverage_percent": round(coverage * 100 / len(vocab), 1),
        "outputs": [artifact.to_report(sha256(artifact.path)) for artifact in artifacts],
    }


def verify(level: str, formats: Sequence[str] = ()) -> dict[str, Any]:
    level_dir = GENERATED / level.lower()
    vocab = json.loads((level_dir / "vocabulary.json").read_text(encoding="utf-8"))
    kanji = json.loads((level_dir / "kanji.json").read_text(encoding="utf-8"))
    recorded = json.loads((level_dir / "report.json").read_text(encoding="utf-8"))
    selected = set(formats)
    outputs = [output for output in recorded["outputs"] if not selected or output["format"] in selected]
    if selected - {output["format"] for output in outputs}:
        missing = ", ".join(sorted(selected - {output["format"] for output in outputs}))
        raise RuntimeError(f"Generated report does not contain requested formats: {missing}")
    artifacts = [DeckArtifact.from_report(DIST, output) for output in outputs]
    report = validate(level, vocab, kanji, artifacts)
    if selected:
        expected = {key: value for key, value in recorded.items() if key != "outputs"}
        expected["outputs"] = outputs
    else:
        expected = recorded
    if report != expected:
        raise RuntimeError("Generated artifacts do not match report.json; rebuild the level")
    return report


def build(level: str, formats: Sequence[str] = ()) -> dict[str, Any]:
    jmdict = read_zip_json(CACHE / "dictionary" / "jmdict_examples.zip")
    kdic_data = read_zip_json(CACHE / "dictionary" / "kanjidic2.zip")
    krad_data = read_zip_json(CACHE / "dictionary" / "kradfile.zip")
    vocab = vocabulary_records(level, jmdict)
    kanji = kanji_records(level, source_kanji(level), kanjidic_index(kdic_data), krad_data["kanji"], vocab)
    level_dir = GENERATED / level.lower()
    level_dir.mkdir(parents=True, exist_ok=True)
    (level_dir / "vocabulary.json").write_text(json_dump(vocab), encoding="utf-8")
    (level_dir / "kanji.json").write_text(json_dump(kanji), encoding="utf-8")
    write_csv(level_dir / "vocabulary.csv", vocab, ["id", "level", "order", "source_order", "curriculum", "written", "reading", "meanings", "parts_of_speech", "common", "examples", "provenance"])
    write_csv(level_dir / "kanji.csv", kanji, ["id", "level", "order", "source_order", "character", "meanings", "readings", "strokes", "grade", "frequency_rank", "classical_radical_numbers", "radical_names", "components", "atomic_component", "example_words", "provenance"])
    artifacts = [
        artifact
        for exporter in select_exporters(formats)
        for artifact in exporter.export(level, vocab, kanji, DIST)
    ]
    report = validate(level, vocab, kanji, artifacts)
    (level_dir / "report.json").write_text(json_dump(report), encoding="utf-8")
    return report

