# Agent guide

- Never call these lists official; the JLPT publishes no exact current item inventory.
- Keep upstream inputs pinned by immutable revision, row count and SHA-256 in `sources.lock.json`.
- Put reviewed aliases/suppressions in `curation/overrides.json`, not transformation code.
- Use sourced, sense-linked examples. Do not fabricate examples or match them by raw substring.
- Do not commit generated data, decks, caches or release artifacts.
- Preserve deterministic output: stable ordering, timestamps, serialization and checksums.
- Update `SOURCES.md`, `NOTICE.md` and `docs/SCHEMA.md` when provenance or fields change.
- Before committing, run unit tests plus `all` and `verify` for every affected level.
- Publish distributable files only through `.github/workflows/release.yml`.
