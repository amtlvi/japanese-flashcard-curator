import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import flashcard_curator as curator


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
            curator.write_mochi(path, (("Test", ["a\n\n---\n\nb", "c\n\n---\n\nd"]),))
            with zipfile.ZipFile(path) as archive:
                root = curator.decode_transit_map(json.loads(archive.read("data.json")))
            cards = curator.decode_transit_map(root["decks"][0])["cards"]
            self.assertEqual([curator.decode_transit_map(c)["pos"] for c in cards], ["000001", "000002"])

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
