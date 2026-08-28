# Canonical data schema

JSON is canonical; CSV mirrors the same nested values as JSON strings. Field names are deliberately level-agnostic so the same pipeline can build N1–N5 or a future non-JLPT list adapter.

## Vocabulary record

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | Stable generated ID, e.g. `n5-vocab-0001` |
| `level` | string | Source level (`N5`…`N1`) |
| `order` | integer | Final learnable deck order |
| `source_order` | integer | Row position in the pinned level map |
| `curriculum.genki_lesson` | integer/null | Lesson tag when supplied by the map |
| `written.primary` | string | Preferred source spelling |
| `written.variants` | string[] | All source spellings |
| `written.without_furigana` | string | Plain display/copy spelling |
| `written.with_furigana` | string | Canonical ruby markup; rendered appropriately by each exporter |
| `written.lookup_text` | string | Plain dictionary lookup form without affix marker |
| `reading.primary` | string | Cleaned preferred reading |
| `reading.variants` | string[] | Cleaned alternate readings |
| `reading.source_text` | string | Original unmodified source reading for audit |
| `meanings` | string[] | English source-list translations/glosses |
| `parts_of_speech` | object[] | JMdict POS code and human-readable label |
| `common` | boolean | JMdict common-word flag |
| `examples` | object[] | Zero to two short, sense-linked examples |
| `examples[].japanese_raw` | string | Plain Japanese safe to copy; never contains furigana markup |
| `examples[].japanese_furigana` | string | Mochi automatic-furigana component around the sentence |
| `examples[].english` | string | Tatoeba English translation |
| `examples[].source` | string | Example provider (`tatoeba`) |
| `examples[].source_id` | string | Upstream sentence identifier |
| `provenance.level_map` | string | Level-map source name |
| `provenance.level_map_guid` | string | Stable source-row GUID when present |
| `provenance.dictionary` | string | Dictionary source name |
| `provenance.dictionary_entry_id` | string/null | JMdict entry ID |
| `provenance.dictionary_lookup_aliases` | string[] | Reviewed aliases used only for dictionary matching |
| `provenance.examples` | string/null | Example provenance statement |

## Kanji record

| Field | Type | Meaning |
| --- | --- | --- |
| `id`, `level`, `order`, `source_order` | mixed | Same roles as vocabulary records |
| `character` | string | Kanji literal |
| `meanings` | string[] | English KANJIDIC2 meanings |
| `readings.onyomi` | string[] | On readings |
| `readings.kunyomi` | string[] | Kun readings |
| `readings.nanori` | string[] | Name readings |
| `strokes` | integer/null | Primary stroke count |
| `grade` | integer/null | Japanese school grade when available |
| `frequency_rank` | integer/null | KANJIDIC2 newspaper frequency rank |
| `classical_radical_numbers` | string[] | Classical radical number(s) |
| `radical_names` | string[] | Radical names when supplied |
| `components` | object[] | KRADFILE visible component symbols and up to three KANJIDIC2 glosses |
| `atomic_component` | boolean | True when KRADFILE has no smaller visible component after self-filtering |
| `example_words` | object[] | Up to five level vocabulary items containing the character, with raw/furigana forms, reading, and meanings |
| `provenance` | object | Level-map, dictionary, and component sources |

## Rendering

The `.mochi` file is a ZIP with compact Transit JSON in `data.json`. Each card contains only documented import essentials: Markdown `content` and a zero-padded `pos`. Vocabulary fronts are plain headwords. Backs carry annotated form, reading, translations, POS, examples, and a fenced raw Japanese block. Kanji backs carry readings, meanings, stats, graphical components, example words, and a raw block.

The `.apkg` file contains separate semantic Anki fields and note types for vocabulary and kanji. Headwords and example words use HTML ruby; examples retain separate Japanese and English content plus a raw copy field. See [`EXPORTERS.md`](EXPORTERS.md) for the format contract and Anki-specific limitations.
