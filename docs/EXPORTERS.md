# Exporter architecture

The curation pipeline produces one canonical vocabulary list and one canonical kanji list per level. Output formats are adapters over those records; exporters must not re-fetch, reclassify or silently alter source data.

## Contract

An exporter implements the protocol in `japanese_flashcard_curator/exporters/base.py`:

- `name` and `extension` identify the format.
- `export(level, vocabulary, kanji, output_dir)` writes files and returns `DeckArtifact` metadata.
- `validate(artifact)` performs format-specific structural and count checks.

Register one exporter instance in `exporters/__init__.py`. Build reports and release packaging consume `DeckArtifact` metadata, so no other filename lists should need changing.

Every exporter must produce `vocabulary`, `kanji` and `complete` scopes, use stable IDs/order, avoid scheduling history, write atomically, and be byte-identical for identical inputs.

## Built-in formats

### Mochi

Compact Transit JSON in a deterministic `.mochi` ZIP. Cards use Mochi Markdown and its automatic sentence-furigana component.

### Anki

Legacy-compatible `.apkg` ZIP containing `collection.anki2` and an empty media map. It uses separate vocabulary and kanji note types with editable semantic fields, stable GUIDs, HTML ruby for headwords/example words, and new-card positions matching canonical order. Tatoeba sentence examples remain plain Japanese because the source does not provide reliable full-sentence readings.

## CLI

Build every registered format by default, or select formats explicitly:

```bash
python3 flashcard_curator.py build --level N5
python3 flashcard_curator.py build --level N5 --format anki
python3 flashcard_curator.py verify --level N5 --format anki
```
