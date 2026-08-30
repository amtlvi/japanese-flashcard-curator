# Japanese Flashcard Curator

Builds deterministic JLPT vocabulary and kanji decks for Anki and Mochi from pinned community level maps, JMdict, KANJIDIC2, KRADFILE and Tatoeba examples.

> Purely vibe-coded. Suggestions and improvements are welcome.

## Download

Most learners need one complete file for their level:

| Level | Anki | Mochi |
| --- | --- | --- |
| N5 | [`.apkg`](https://github.com/amtlvi/japanese-flashcard-curator/releases/latest/download/jlpt_n5_complete.apkg) | [`.mochi`](https://github.com/amtlvi/japanese-flashcard-curator/releases/latest/download/jlpt_n5_complete.mochi) |
| N4 | [`.apkg`](https://github.com/amtlvi/japanese-flashcard-curator/releases/latest/download/jlpt_n4_complete.apkg) | [`.mochi`](https://github.com/amtlvi/japanese-flashcard-curator/releases/latest/download/jlpt_n4_complete.mochi) |
| N3 | [`.apkg`](https://github.com/amtlvi/japanese-flashcard-curator/releases/latest/download/jlpt_n3_complete.apkg) | [`.mochi`](https://github.com/amtlvi/japanese-flashcard-curator/releases/latest/download/jlpt_n3_complete.mochi) |
| N2 | [`.apkg`](https://github.com/amtlvi/japanese-flashcard-curator/releases/latest/download/jlpt_n2_complete.apkg) | [`.mochi`](https://github.com/amtlvi/japanese-flashcard-curator/releases/latest/download/jlpt_n2_complete.mochi) |
| N1 | [`.apkg`](https://github.com/amtlvi/japanese-flashcard-curator/releases/latest/download/jlpt_n1_complete.apkg) | [`.mochi`](https://github.com/amtlvi/japanese-flashcard-curator/releases/latest/download/jlpt_n1_complete.mochi) |

Vocabulary-only, kanji-only, canonical data and checksums are on the [release page](https://github.com/amtlvi/japanese-flashcard-curator/releases/latest). Cards include readings, meanings, furigana, sourced examples, raw copyable Japanese, per-word kanji meaning clues and kanji components.

### Upgrade an imported Mochi deck

Mochi does not reliably merge imported cards whose IDs already exist, including IDs held by a deck in Trash. Upgrading is therefore a backup-preserving replacement, not an in-place merge.

Export a fresh native `.mochi` backup of each current deck. Download the matching vocabulary-only or kanji-only release file, then build a replacement:

```bash
uv run flashcard-curator mochi-upgrade current-vocabulary.mochi jlpt_n5_vocabulary.mochi --output updated-vocabulary.mochi
```

The replacement preserves the native deck/card IDs, review history, templates, metadata and attachments while updating content/order. It adds new cards, retains cards removed from the release, and removes frequency tags accidentally created by older cards.

Keep the original export as a recovery backup. In Mochi, delete the old deck **and permanently remove it from Trash** to release its IDs, then import the replacement. If import fails, restore the original native backup. Repeat separately for vocabulary and kanji decks.

## Develop

Install [uv](https://docs.astral.sh/uv/), then:

```bash
uv sync --locked
uv run flashcard-curator all --level N5
uv run flashcard-curator verify --level N5
uv run python -m unittest discover -s tests -v
```

All exporters run by default; add `--format anki` or `--format mochi` to select one. Outputs go to ignored `data/`, `dist/` and `release-artifacts/` directories.

```text
src/japanese_flashcard_curator/
├── curator.py       source fetching and canonical record construction
├── cli.py           command-line interface
├── exporters/       Anki/Mochi adapters and validators
└── data/            pinned checksums and reviewed curation overrides
```

The JLPT does not publish a definitive post-2010 item list; these decks use pinned community mappings. Vocabulary comes from [open-anki-jlpt-decks](https://github.com/jamsinclair/open-anki-jlpt-decks), kanji levels from [JLPT_Vocabulary](https://github.com/Bluskyo/JLPT_Vocabulary), dictionary/components from [EDRDG](https://www.edrdg.org/edrdg/licence.html), and examples from [Tatoeba](https://tatoeba.org/en/terms_of_use). Exact revisions, row counts and SHA-256 values live in `src/japanese_flashcard_curator/data/sources.lock.json`.

Code is MIT. Generated data retains upstream attribution and licensing: level-list normalization is MIT/CC BY-derived, JMdict/KANJIDIC2/KRADFILE is CC BY-SA 4.0, and Tatoeba examples are CC BY 2.0 FR.
