# Japanese Flashcard Curator

Builds deterministic Anki and Mochi decks for JLPT vocabulary and kanji. It combines pinned community JLPT level maps with JMdict, KANJIDIC2, KRADFILE and sense-linked Tatoeba examples.

## Download a deck

Most learners should download **one complete deck** for their level and app:

| Level | Anki | Mochi |
| --- | --- | --- |
| N5 | [`jlpt_n5_complete.apkg`](https://github.com/amtlvi/japanese-flashcard-curator/releases/latest/download/jlpt_n5_complete.apkg) | [`jlpt_n5_complete.mochi`](https://github.com/amtlvi/japanese-flashcard-curator/releases/latest/download/jlpt_n5_complete.mochi) |
| N4 | [`jlpt_n4_complete.apkg`](https://github.com/amtlvi/japanese-flashcard-curator/releases/latest/download/jlpt_n4_complete.apkg) | [`jlpt_n4_complete.mochi`](https://github.com/amtlvi/japanese-flashcard-curator/releases/latest/download/jlpt_n4_complete.mochi) |
| N3 | [`jlpt_n3_complete.apkg`](https://github.com/amtlvi/japanese-flashcard-curator/releases/latest/download/jlpt_n3_complete.apkg) | [`jlpt_n3_complete.mochi`](https://github.com/amtlvi/japanese-flashcard-curator/releases/latest/download/jlpt_n3_complete.mochi) |
| N2 | [`jlpt_n2_complete.apkg`](https://github.com/amtlvi/japanese-flashcard-curator/releases/latest/download/jlpt_n2_complete.apkg) | [`jlpt_n2_complete.mochi`](https://github.com/amtlvi/japanese-flashcard-curator/releases/latest/download/jlpt_n2_complete.mochi) |
| N1 | [`jlpt_n1_complete.apkg`](https://github.com/amtlvi/japanese-flashcard-curator/releases/latest/download/jlpt_n1_complete.apkg) | [`jlpt_n1_complete.mochi`](https://github.com/amtlvi/japanese-flashcard-curator/releases/latest/download/jlpt_n1_complete.mochi) |

Vocabulary-only, kanji-only, canonical JSON/CSV and checksums are on the [latest release page](https://github.com/amtlvi/japanese-flashcard-curator/releases/latest).

## Card content

- Vocabulary: written form, furigana, reading, English meanings, part of speech, sourced examples and raw copyable Japanese.
- Kanji: meanings, readings, strokes, frequency, visible KRADFILE components and example words.
- Ordering: Genki lesson tags where available, then JMdict common-word status; kanji use KANJIDIC2 frequency.

Anki exports use editable semantic fields and stable note IDs. Mochi exports use Markdown and automatic sentence furigana. Tatoeba sentence examples in Anki remain plain Japanese because the source does not provide reliable full-sentence readings.

## How it works

1. Fetch files pinned by immutable revision and SHA-256 in [`sources.lock.json`](sources.lock.json).
2. Join level maps with dictionary, example and component data.
3. Apply reviewed exceptions from [`curation/overrides.json`](curation/overrides.json).
4. Pass canonical records to registered format exporters.
5. Validate counts, ordering and each package’s internal structure.

Identical inputs produce byte-identical outputs. The JLPT does not publish an exact current vocabulary or kanji syllabus, so these are community mappings rather than official lists. See [`SOURCES.md`](SOURCES.md), [`docs/SCHEMA.md`](docs/SCHEMA.md) and [`docs/EXPORTERS.md`](docs/EXPORTERS.md).

## Build locally

Python 3.11+; no third-party runtime packages are required.

```bash
python3 flashcard_curator.py all --level N5
python3 flashcard_curator.py verify --level N5
python3 flashcard_curator.py package --level N5
python3 -m unittest discover -s tests -v
```

All registered formats are built by default. Use `--format anki` or `--format mochi` to select one; repeat `--level` or `--format` as needed. Generated files are ignored and distributed through GitHub Releases.

> Disclaimer: This is a purely vibe-coded project, but suggestions for improvements and additions are very welcome.

Code is MIT licensed. Generated data retains upstream licensing and attribution; see [`NOTICE.md`](NOTICE.md).
