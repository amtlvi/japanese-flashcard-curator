# Sources and selection rationale

## Why this is not called an official exact syllabus

The current JLPT describes what each level measures but does not publish a definitive post-2010 vocabulary/kanji inventory. Counts presented here are therefore the exact counts of the pinned community mappings, not an assertion that the test owner guarantees those items.

Official level description: <https://www.jlpt.jp/e/about/levelsummary.html>

## Level maps

### Vocabulary

- Project: [jamsinclair/open-anki-jlpt-decks](https://github.com/jamsinclair/open-anki-jlpt-decks)
- Pinned commit: `1ad66734417aca9dbcca6b2d5ee440cb13ab3ba0`
- N5 rows: 718
- Rationale: a maintained, reviewable CSV project with stable GUIDs and curriculum tags; it traces its base lists through earlier open JLPT decks to Tanos/Jonathan Waller.
- License: repository code/list normalization MIT; underlying Tanos list attribution retained.

### Kanji

- Project: [Bluskyo/JLPT_Vocabulary](https://github.com/Bluskyo/JLPT_Vocabulary)
- Pinned commit: `4358f932937ad0232194a36e9f4f875094910c6b`
- N5 rows: 79
- Rationale: lossless parsed JLPT kanji data with explicit attribution to Jonathan Waller/Tanos.
- License: parser repository MIT; source data Creative Commons Attribution by Jonathan Waller, as declared by the repository.

## Dictionary, examples, and components

- Project: [scriptin/jmdict-simplified](https://github.com/scriptin/jmdict-simplified)
- Pinned release: `3.6.2+20260824122934` (dictionary date 2026-08-24)
- Assets: JMdict with sense-linked English examples, KANJIDIC2 English, and KRADFILE; exact SHA-256 values are in [`sources.lock.json`](sources.lock.json).
- JMdict supplies dictionary identity, form/readings, common flags, parts of speech, and sense restrictions.
- Tatoeba supplies Japanese/English sentence pairs carried by JMdict’s sense-linked examples. The builder keeps examples only from senses applicable to the target form/reading, de-duplicates them, then chooses the shortest two deterministically. A small reviewed suppression list handles known cases where a shared kanji spelling would demonstrate a different reading.
- KANJIDIC2 supplies kanji readings, meanings, strokes, grade, radicals, and frequency rank.
- KRADFILE supplies visible graphical components. Component meanings are looked up in KANJIDIC2 when the component is also encoded as a character.
- License: JMdict, KANJIDIC2, and KRADFILE are distributed by EDRDG under CC BY-SA 4.0; Tatoeba example sentences are CC BY 2.0 FR. See <https://www.edrdg.org/edrdg/licence.html> and <https://tatoeba.org/en/terms_of_use>.

## Rejected approaches

- Treating every dictionary word containing an N5 kanji as N5 vocabulary. That produced the earlier 7,773-card deck and is not a valid level mapping.
- Presenting any unofficial mapping as the exact official list.
- Raw substring sentence matching. It can match across Japanese word boundaries and attach unrelated examples.
- Generating example sentences while presenting them as sourced. Missing source examples remain missing.

## Updating sources

Do not silently follow a moving branch. Review a new upstream revision, update the pinned commit/release and per-file SHA-256/row count in [`sources.lock.json`](sources.lock.json), rebuild, inspect the report, and commit the lock change together with generated artifacts.
