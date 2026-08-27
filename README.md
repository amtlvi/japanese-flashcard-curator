# Flashcard Curator

Reproducible JLPT vocabulary and kanji curation with deterministic Mochi exports.

## Important scope note

The JLPT publishes skill-level summaries, not an official post-2010 itemized vocabulary or kanji syllabus. This project therefore does **not** label any community list as “the exact official list.” It uses pinned, reviewable community level maps and enriches them from maintained dictionary projects. Every upstream file is locked by commit or release tag and SHA-256 in [`sources.lock.json`](sources.lock.json).

The current checked-in build is JLPT N5:

| Artifact | Count | Purpose |
| --- | ---: | --- |
| [`dist/jlpt_n5_complete.mochi`](dist/jlpt_n5_complete.mochi) | 718 vocabulary + 79 kanji | Recommended import |
| [`dist/jlpt_n5_vocabulary.mochi`](dist/jlpt_n5_vocabulary.mochi) | 718 | Vocabulary only |
| [`dist/jlpt_n5_kanji.mochi`](dist/jlpt_n5_kanji.mochi) | 79 | Kanji only |
| [`data/generated/n5/vocabulary.json`](data/generated/n5/vocabulary.json) | 718 | Canonical machine-readable records |
| [`data/generated/n5/kanji.json`](data/generated/n5/kanji.json) | 79 | Canonical machine-readable records |

The build matched all 718 vocabulary rows to JMdict. Of those, 697 have one or two JMdict sense-linked Tatoeba examples. Missing examples remain explicitly missing rather than being fabricated.

## Learnable ordering

Vocabulary cards are ordered by:

1. Genki lesson number when the pinned level map provides one;
2. JMdict’s common-word flag for the remainder;
3. original source order as a deterministic tie-breaker.

The first words are `医者`, `今`, `妹`, `英語`, `ええ`, `お母さん`, `お父さん`, `弟`, `お兄さん`, and `お姉さん`—all tagged as Genki Lesson 1. Kanji are ordered by KANJIDIC2 newspaper frequency rank, with source order as fallback.

## Card design

Vocabulary cards show the plain written form on the front. The back includes explicit Mochi furigana, reading, English meanings, part of speech, up to two short sense-linked examples with automatic sentence furigana, and the same Japanese examples as raw text in a fenced `text` block for clean copying into Yomiwa or another dictionary.

Kanji cards include English meanings, on/kun readings, stroke count, grade, frequency rank, classical radical number, KRADFILE visible components, component glosses when available, example words, and a raw copy block. KRADFILE components are graphical components, not claims about character etymology.

See [`docs/SCHEMA.md`](docs/SCHEMA.md) for every canonical field and [`SOURCES.md`](SOURCES.md) for provenance and licensing.

## Rebuild

Python 3.11 or newer is the only runtime requirement.

```bash
python3 flashcard_curator.py all --level N5
python3 flashcard_curator.py verify --level N5
python3 -m unittest discover -s tests -v
```

To build more lists, repeat `--level`:

```bash
python3 flashcard_curator.py all --level N5 --level N4 --level N3
```

The source lock already contains N1–N5 mappings. Intentional spelling aliases belong in [`curation/overrides.json`](curation/overrides.json), keeping curation separate from transformation code.

## Determinism and validation

Downloads are rejected when their SHA-256 differs from the lock. The builder checks exact source counts, unique IDs, contiguous ordering, raw-example cleanliness, Mochi ZIP/Transit shape, and card positions. Mochi archives use a fixed ZIP timestamp and compact Transit JSON, so identical inputs produce byte-identical packages.

The archives are structurally validated here, but application-level import still depends on Mochi itself.

## License

The curator code is MIT licensed. Generated data contains material under upstream licenses, including CC BY and CC BY-SA; see [`NOTICE.md`](NOTICE.md) before redistributing.
