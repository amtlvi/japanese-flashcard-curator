# Japanese Flashcard Curator

Builds deterministic [Mochi](https://mochi.cards/) decks for JLPT vocabulary and kanji. It combines pinned community JLPT level maps with JMdict, KANJIDIC2, KRADFILE, and sense-linked Tatoeba examples.

## Download a deck

Most learners should download **one complete deck** for their level:

| Level | Download |
| --- | --- |
| N5 | [`jlpt_n5_complete.mochi`](https://github.com/amtlvi/japanese-flashcard-curator/releases/latest/download/jlpt_n5_complete.mochi) |
| N4 | [`jlpt_n4_complete.mochi`](https://github.com/amtlvi/japanese-flashcard-curator/releases/latest/download/jlpt_n4_complete.mochi) |
| N3 | [`jlpt_n3_complete.mochi`](https://github.com/amtlvi/japanese-flashcard-curator/releases/latest/download/jlpt_n3_complete.mochi) |
| N2 | [`jlpt_n2_complete.mochi`](https://github.com/amtlvi/japanese-flashcard-curator/releases/latest/download/jlpt_n2_complete.mochi) |
| N1 | [`jlpt_n1_complete.mochi`](https://github.com/amtlvi/japanese-flashcard-curator/releases/latest/download/jlpt_n1_complete.mochi) |

Vocabulary-only, kanji-only, canonical JSON/CSV, and checksums are available on the [latest release page](https://github.com/amtlvi/japanese-flashcard-curator/releases/latest).

## What is on each card?

- Vocabulary: written form, furigana, reading, English meanings, part of speech, sourced examples and a raw Japanese copy block.
- Kanji: meanings, readings, strokes, frequency, visible KRADFILE components and example words.
- Ordering: Genki lesson tags where available, then JMdict common-word status; kanji use KANJIDIC2 frequency.

## How it works

1. Download files pinned by commit/release and SHA-256 in [`sources.lock.json`](sources.lock.json).
2. Join the level maps with dictionary, example and component data.
3. Apply reviewed exceptions from [`curation/overrides.json`](curation/overrides.json).
4. Validate counts, IDs, ordering, raw text and Mochi structure.
5. Produce byte-identical Mochi and data archives for identical inputs.

The JLPT does not publish an exact current vocabulary or kanji syllabus. These are pinned community level mappings, not official lists. Full provenance is in [`SOURCES.md`](SOURCES.md); the record format is in [`docs/SCHEMA.md`](docs/SCHEMA.md).

## Build locally

Python 3.11+; no third-party runtime packages are required.

```bash
python3 flashcard_curator.py all --level N5
python3 flashcard_curator.py verify --level N5
python3 flashcard_curator.py package --level N5
python3 -m unittest discover -s tests -v
```

Repeat `--level` to build multiple levels. Generated files are ignored and distributed through GitHub Releases.

> Disclaimer: This is a purely vibe-coded project, but suggestions for improvements and additions are very welcome.

Code is MIT licensed. Generated data retains upstream licensing and attribution; see [`NOTICE.md`](NOTICE.md).
