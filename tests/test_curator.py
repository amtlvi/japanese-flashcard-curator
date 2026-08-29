import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from japanese_flashcard_curator import curator
from japanese_flashcard_curator.exporters import available_formats
from japanese_flashcard_curator.exporters.anki import AnkiExporter, mochi_furigana_to_html
from japanese_flashcard_curator.exporters.mochi import (
    MochiExporter,
    _write_transit_archive,
    kanji_card,
    prepare_mochi_update,
    read_mochi,
    transit_keyword,
    transit_map,
    write_mochi,
)


class FuriganaTests(unittest.TestCase):
    def test_okurigana(self):
        self.assertEqual(curator.explicit_furigana("食べる", "たべる"), "{食}(た)べる")

    def test_multi_anchor(self):
        self.assertEqual(curator.explicit_furigana("取り替える", "とりかえる"), "{取}(と)り{替}(か)える")

    def test_kana_only(self):
        self.assertEqual(curator.explicit_furigana("あさって", "あさって"), "あさって")

    def test_affix(self):
        self.assertEqual(curator.explicit_furigana("〜円", "〜えん"), "〜{円}(えん)")

    def test_source_reading_hints_are_removed(self):
        self.assertEqual(curator.clean_source_reading("(〜を) とお"), "とお")
        self.assertEqual(curator.clean_source_reading("べんきょう (する)"), "べんきょう")


class FormatTests(unittest.TestCase):
    @staticmethod
    def sample_vocabulary():
        return {
            "id": "n5-vocab-0001",
            "level": "N5",
            "order": 1,
            "written": {
                "without_furigana": "食べる",
                "with_furigana": "{食}(た)べる",
                "lookup_text": "食べる",
            },
            "reading": {"primary": "たべる"},
            "meanings": ["to eat"],
            "parts_of_speech": [{"label": "Ichidan verb"}],
            "common": True,
            "examples": [
                {
                    "japanese_raw": "寿司を食べる。",
                    "japanese_furigana": "寿司を{食}(た)べる。",
                    "english": "I eat sushi.",
                }
            ],
            "provenance": {"dictionary_entry_id": "1358280"},
        }

    @staticmethod
    def sample_kanji():
        return {
            "id": "n5-kanji-0001",
            "level": "N5",
            "order": 1,
            "character": "食",
            "meanings": ["eat", "food"],
            "readings": {"onyomi": ["ショク"], "kunyomi": ["た.べる"]},
            "strokes": 9,
            "grade": 2,
            "frequency_rank": 328,
            "components": [{"symbol": "人", "meanings": ["person"]}],
            "example_words": [
                {
                    "written_raw": "食べる",
                    "written_furigana": "{食}(た)べる",
                    "reading": "たべる",
                    "meanings": ["to eat"],
                }
            ],
        }

    def test_variant_split(self):
        self.assertEqual(curator.split_variants("足; 脚"), ["足", "脚"])

    def test_examples_are_shortest_first(self):
        senses = [{"examples": [
            {"sentences": [{"lang": "jpn", "text": "これは長い例です。"}, {"lang": "eng", "text": "Long."}]},
            {"sentences": [{"lang": "jpn", "text": "短い。"}, {"lang": "eng", "text": "Short."}]},
        ]}]
        self.assertEqual(curator.sense_examples(senses, limit=1)[0]["japanese_raw"], "短い。")


    def test_mochi_positions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.mochi"
            write_mochi(path, (("Test", ["a\n\n---\n\nb", "c\n\n---\n\nd"]),))
            root = read_mochi(path)
            self.assertEqual([card["pos"] for card in root["cards"]], ["000001", "000002"])

    def test_mochi_frequency_is_not_a_tag(self):
        content = kanji_card(self.sample_kanji())
        self.assertIn("Frequency rank: 328", content)
        self.assertNotIn("#328", content)

    def test_mochi_source_hash_is_escaped(self):
        record = self.sample_vocabulary()
        record["meanings"] = ["#1"]
        from japanese_flashcard_curator.exporters.mochi import vocabulary_card

        self.assertIn("- \\#1", vocabulary_card(record))

    def test_mochi_packages_are_valid_and_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            exporter = MochiExporter()
            artifacts = exporter.export("N5", [self.sample_vocabulary()], [self.sample_kanji()], root)
            first = {artifact.path.name: artifact.path.read_bytes() for artifact in artifacts}
            self.assertTrue(all(exporter.validate(artifact) == [] for artifact in artifacts))
            artifacts = exporter.export("N5", [self.sample_vocabulary()], [self.sample_kanji()], root)
            self.assertEqual(first, {artifact.path.name: artifact.path.read_bytes() for artifact in artifacts})

    def test_mochi_upgrade_reuses_imported_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            existing = root / "existing.mochi"
            release = root / "release.mochi"
            update = root / "update.mochi"
            old_content = "# 食\n\n---\n\nOld back"
            old_card = transit_map((
                ("id", transit_keyword("ExistingCard01")),
                ("content", old_content),
                ("pos", "000001"),
            ))
            old_deck = transit_map((
                ("id", transit_keyword("ExistingDeck01")),
                ("name", "JLPT N5 Kanji"),
                ("cards", [old_card]),
            ))
            _write_transit_archive(
                existing, transit_map((("version", 2), ("decks", [old_deck])))
            )
            write_mochi(
                release,
                (("JLPT N5 Kanji", (("n5-kanji-0001", "# 食\n\n---\n\nNew back"),)),),
            )
            report = prepare_mochi_update(existing, release, update)
            cards = read_mochi(update)["cards"]
            self.assertEqual(report, {"updated": 1, "added": 0, "retained": 0})
            self.assertEqual(cards[0]["id"], "ExistingCard01")
            self.assertEqual(cards[0]["deck-id"], "ExistingDeck01")
            self.assertNotIn("reviews", cards[0])

    def test_exporter_registry(self):
        self.assertEqual(available_formats(), ("anki", "mochi"))

    def test_anki_ruby_conversion(self):
        self.assertEqual(
            mochi_furigana_to_html("{取}(と)り{替}(か)える", "取り替える", "とりかえる"),
            "<ruby>取<rt>と</rt></ruby>り<ruby>替<rt>か</rt></ruby>える",
        )

    def test_anki_packages_are_valid_and_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            exporter = AnkiExporter()
            artifacts = exporter.export("N5", [self.sample_vocabulary()], [self.sample_kanji()], root)
            first = {artifact.path.name: artifact.path.read_bytes() for artifact in artifacts}
            for artifact in artifacts:
                self.assertEqual(exporter.validate(artifact), [])
                with zipfile.ZipFile(artifact.path) as archive:
                    self.assertEqual(archive.namelist(), ["collection.anki2", "media"])
            artifacts = exporter.export("N5", [self.sample_vocabulary()], [self.sample_kanji()], root)
            self.assertEqual(first, {artifact.path.name: artifact.path.read_bytes() for artifact in artifacts})

    def test_data_archive_metadata_is_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "n5"
            source.mkdir()
            for name in ("vocabulary.json", "vocabulary.csv", "kanji.json", "kanji.csv", "report.json"):
                (source / name).write_text(name, encoding="utf-8")
            old_generated = curator.GENERATED
            try:
                curator.GENERATED = root
                target = root / "data.zip"
                curator.write_data_archive(target, "N5")
                first = target.read_bytes()
                curator.write_data_archive(target, "N5")
                self.assertEqual(first, target.read_bytes())
                with zipfile.ZipFile(target) as archive:
                    self.assertTrue(all(item.date_time == (1980, 1, 1, 0, 0, 0) for item in archive.infolist()))
            finally:
                curator.GENERATED = old_generated


if __name__ == "__main__":
    unittest.main()
