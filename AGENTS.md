# Agent guide

The canonical pipeline is `src/japanese_flashcard_curator/curator.py`; format-specific rendering belongs in `exporters/`. Add an exporter by implementing `export()` and `validate()` and registering it in `exporters/__init__.py`.

- Never call the community mappings an official JLPT syllabus.
- Pin source revisions, row counts and hashes in `src/japanese_flashcard_curator/data/sources.lock.json`; put reviewed exceptions beside it in `overrides.json`.
- Keep examples sourced and sense-linked. Never fabricate them or match by raw substring.
- Preserve stable ordering, IDs, timestamps, serialization and byte-identical rebuilds.
- Do not commit generated data, decks, caches or release assets.
- Keep the version only in `pyproject.toml`; releases are built by GitHub Actions.
- Use uv: `uv sync --locked`, then run unit tests plus `all` and `verify` for affected levels.
