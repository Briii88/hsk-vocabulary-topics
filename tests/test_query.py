"""Reader checks use synthetic fixtures; snapshot checks require the real data files."""
import copy
from collections import defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("vocabulary_query", ROOT / "query.py")
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)
SNAPSHOT = "sha256:" + "a" * 64
COMMON = {"dataset_snapshot_version": "test-fixture", "source_snapshot_id": SNAPSHOT}


def fixture_tables():
    tables = {name: [] for name in q.TABLE_KEYS}
    for i, (word, base, level) in enumerate((("行1", "行", "1"), ("行2", "行", "3"),
                                            ("路", "路", "4"), ("测试甲", "测试甲", "7-9")), 1):
        key = SNAPSHOT + "::v" + str(i)
        tables["words"].append({**COMMON, "word_key": key, "vocab_id": "v" + str(i),
                                "written_form": word, "written_form_base": base,
                                "pinyin_source": "test" + str(i), "base_level_band": level,
                                "source_sequence": i, "all_senses_complete": False})
        tables["stages"].append({**COMMON, "word_key": key, "stage_id": "stage" + str(i),
                                 "stage_kind": "base", "level_band": level})
    tables["stages"].append({**COMMON, "word_key": tables["words"][0]["word_key"],
                             "stage_id": "extension1", "stage_kind": "extension", "level_band": "5"})
    for index, (class_id, theme_id) in enumerate((("A", "T1"), ("B", "T2"), ("C", "T1"), ("A", "T1"))):
        tables["relations"].append({
            **COMMON, "word_key": tables["words"][index]["word_key"],
            "relation_key": "rk" + str(index), "relation_id": "r" + str(index),
            "class_id": class_id, "theme_id": theme_id, "current_research_state": "accepted_local_research",
            "selected_meaning": "synthetic selected meaning", "scene": [], "use": ["synthetic use"],
            "restriction": "Only this selected sense and context.", "classification_rationale": "fixture reason",
            "scope_notes": [{"role": "historical", "original_field": "status", "value": "pending"}],
        })
    tables["themes"] = [{**COMMON, "theme_id": "T1", "name": "主题甲"},
                        {**COMMON, "theme_id": "T2", "name": "主题乙"}]
    tables["taxonomy"] = [{**COMMON, "class_id": "A", "name": "类甲", "aliases": ["old-A"]},
                          {**COMMON, "class_id": "B", "name": "重名", "aliases": []},
                          {**COMMON, "class_id": "C", "name": "重名", "aliases": []}]
    first = tables["words"][0]["word_key"]
    tables["source_notes"] = [{**COMMON, "word_key": first, "note_id": "n1",
                               "adopted_project_interpretation": "fixture interpretation"}]
    tables["classification_dispositions"] = [{**COMMON, "word_key": first, "issue_id": "d1",
                                              "scope_not_closed": "Other senses remain open."}]
    tables["source_differences"] = [{
        "dataset_snapshot_version": "test-fixture", "local_source_snapshot_id": SNAPSHOT,
        "website_source_snapshot_id": "sha256:" + "b" * 64, "comparison_id": "diff1",
        "local_word_key": first, "website_source_sequence": 999,
        "adoption_state": "observed_not_adopted", "field": "pinyin", "review_note": "fixture",
    }]
    return tables


def write_fixture(folder, tables):
    entries = []
    for name, rows in tables.items():
        raw = b"".join((json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8") for row in rows)
        filename = name + ".jsonl"
        (folder / filename).write_bytes(raw)
        entries.append({"path": filename, "bytes": len(raw), "rows": len(rows),
                        "sha256": hashlib.sha256(raw).hexdigest()})
    (folder / "manifest.json").write_text(json.dumps({**COMMON, "files": entries}), encoding="utf-8")


class ReaderUnitTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.folder = Path(self.temporary.name)
        self.tables = fixture_tables()
        write_fixture(self.folder, self.tables)
        self.data = q.Vocabulary(self.folder)

    def tearDown(self):
        self.temporary.cleanup()

    def test_homographs_remain_separate_with_all_metadata(self):
        result = self.data.word("行")
        self.assertEqual(result["total_matching_words"], 2)
        self.assertEqual([r["word"]["vocab_id"] for r in result["results"]], ["v1", "v2"])
        first = result["results"][0]
        self.assertEqual(first["relations"], self.tables["relations"][:1])
        self.assertEqual(first["source_notes"], self.tables["source_notes"])
        self.assertEqual(first["classification_dispositions"], self.tables["classification_dispositions"])
        self.assertEqual(first["source_differences"], self.tables["source_differences"])
        self.assertEqual(self.data.word("行1")["total_matching_words"], 1)

    def test_current_acceptance_does_not_filter_historical_pending(self):
        result = self.data.filter(all_words=True)
        self.assertEqual(result["total_matching_relations"], 4)
        self.assertEqual(result["results"][0]["relations"][0]["scope_notes"][0]["value"], "pending")
        tables = copy.deepcopy(self.tables)
        tables["relations"][0]["current_research_state"] = "candidate"
        write_fixture(self.folder, tables)
        with self.assertRaisesRegex(q.DatasetError, "accepted current"):
            q.Vocabulary(self.folder)

    def test_base_cumulative_extension_keep_word_and_stage_counts_separate(self):
        cumulative = self.data.filter(level="3", mode="cumulative")
        self.assertEqual(cumulative["total_matching_words"], 2)
        first = cumulative["results"][0]
        self.assertEqual(len(first["stages"]), 2)
        self.assertEqual(len(first["matched_stages"]), 1)
        self.assertEqual(first["matched_stages"][0]["stage_kind"], "base")
        extension = self.data.filter(level="5", mode="extension")
        self.assertEqual(extension["total_matching_words"], 1)
        self.assertEqual(extension["total_matching_stages"], 1)
        self.assertEqual(extension["results"][0]["matched_stages"][0]["stage_id"], "extension1")
        self.assertEqual(self.data.filter(level="5", mode="base")["total_matching_words"], 0)

    def test_upper_band_is_not_split(self):
        self.assertEqual(self.data.filter(level="7-9")["total_matching_words"], 1)
        self.assertEqual(self.data.filter(level="7-9", mode="cumulative")["total_matching_words"], 4)
        for level in ("7", "8", "9", 7, True):
            with self.subTest(level=level), self.assertRaises(ValueError):
                self.data.filter(level=level)

    def test_default_is_empty_and_all_is_explicit(self):
        self.assertEqual(self.data.filter()["total_matching_words"], 0)
        self.assertEqual(self.data.filter(all_words=True)["total_matching_words"], 4)
        self.assertEqual(self.data.filter(all_words=True, mode="extension")["total_matching_words"], 1)

    def test_related_scope_is_not_synonymy_and_excludes_seeds(self):
        same_class = self.data.related("行")
        same_theme = self.data.related("行", scope="theme")
        self.assertEqual(same_class["total_matching_words"], 1)
        self.assertEqual(same_theme["total_matching_words"], 2)
        self.assertEqual(len(same_class["seed_words"]), 2)
        self.assertIn("not synonymy", same_class["relatedness_notice"])
        self.assertEqual([x["word"]["vocab_id"] for x in same_theme["results"]], ["v3", "v4"])
        self.assertEqual(self.data.related("不存在")["results"], [])

    def test_theme_class_and_alias_filters(self):
        self.assertEqual(self.data.filter(theme="主题甲")["total_matching_words"], 3)
        self.assertEqual(self.data.filter(class_id="old-A")["total_matching_words"], 2)
        self.assertEqual(self.data.filter(theme="T2", class_id="A")["total_matching_words"], 0)
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            self.data.filter(class_id="重名")
        with self.assertRaisesRegex(ValueError, "unknown"):
            self.data.filter(theme="not a theme")

    def test_pagination_totals_and_invalid_arguments(self):
        result = self.data.filter(all_words=True, limit=1, offset=2)
        self.assertEqual(result["total_matching_words"], 4)
        self.assertEqual(result["total_matching_relations"], 4)
        self.assertEqual(result["results"][0]["word"]["vocab_id"], "v3")
        self.assertEqual(self.data.filter(all_words=True, offset=100)["returned_words"], 0)
        for kwargs in ({"limit": True}, {"offset": True}, {"offset": -1}, {"limit": 0},
                       {"limit": 101}, {"all_words": 1}, {"mode": "cumulative"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.data.filter(**kwargs)

    def test_source_sequence_never_remaps_and_results_are_independent(self):
        result = self.data.word("行1")
        first = result["results"][0]
        self.assertEqual(first["word"]["source_sequence"], 1)
        self.assertEqual(first["source_differences"][0]["website_source_sequence"], 999)
        self.assertIn("do not map automatically", result["source_notice"])
        first["relations"][0]["restriction"] = "changed"
        self.assertEqual(self.data.word("行1")["results"][0]["relations"][0]["restriction"],
                         "Only this selected sense and context.")

    def test_manifest_detects_tampering_without_writes(self):
        before = {p.name: p.read_bytes() for p in self.folder.iterdir()}
        self.data.word("行")
        self.data.related("行")
        self.data.themes()
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.folder.iterdir()})
        (self.folder / "words.jsonl").write_bytes(before["words.jsonl"] + b"\n")
        with self.assertRaisesRegex(q.DatasetError, "hash"):
            q.Vocabulary(self.folder)

    def test_duplicate_json_and_missing_table_fail(self):
        manifest = self.folder / "manifest.json"
        manifest.write_text('{"files":[],"files":[]}', encoding="utf-8")
        with self.assertRaisesRegex(q.DatasetError, "duplicate"):
            q.Vocabulary(self.folder)
        write_fixture(self.folder, self.tables)
        (self.folder / "stages.jsonl").unlink()
        with self.assertRaises(OSError):
            q.Vocabulary(self.folder)

    def test_cli_data_dir_both_positions_and_readable_errors(self):
        for args in (("--data-dir", str(self.folder), "word", "--word", "行"),
                     ("word", "--data-dir", str(self.folder), "--word", "行")):
            run = subprocess.run([sys.executable, "-B", str(ROOT / "query.py"), *args],
                                 capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)["total_matching_words"], 2)
        for args in (("filter", "--level", "8"), ("word", "--word", "行", "--limit", "101"),
                     ("filter", "--mode", "cumulative"), ("filter", "--unexpected")):
            run = subprocess.run([sys.executable, "-B", str(ROOT / "query.py"), "--data-dir", str(self.folder), *args],
                                 capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(run.returncode, 2)
            self.assertEqual(run.stdout, "")
            self.assertNotIn("Traceback", run.stderr)


class PublishedSnapshotTests(unittest.TestCase):
    """These tests fail when the real public dataset is missing; no fixture fallback."""

    @classmethod
    def setUpClass(cls):
        cls.data = q.Vocabulary(ROOT / "data")

    def test_release_counts_and_all_current_relations(self):
        expected = {"words": 11000, "stages": 11105, "relations": 11384,
                    "themes": 35, "taxonomy": 6085, "source_notes": 26,
                    "classification_dispositions": 89}
        for table, count in expected.items():
            with self.subTest(table=table):
                self.assertEqual(len(self.data.tables[table]), count)
        result = self.data.filter(all_words=True, limit=1)
        self.assertEqual(result["total_matching_words"], 11000)
        self.assertEqual(result["total_matching_relations"], 11384)
        self.assertEqual(len(self.data.themes()["results"]), 35)

    def test_all_105_extensions_survive_and_do_not_add_base_words(self):
        extensions = [s for s in self.data.tables["stages"] if s["stage_kind"] == "extension"]
        self.assertEqual(len(extensions), 105)
        result = self.data.filter(all_words=True, mode="extension", limit=100)
        self.assertEqual(result["total_matching_words"], len({s["word_key"] for s in extensions}))
        self.assertEqual(result["total_matching_stages"], 105)
        matched = []
        for offset in range(0, result["total_matching_words"], 100):
            page = self.data.filter(all_words=True, mode="extension", limit=100, offset=offset)
            matched.extend(stage["stage_id"] for item in page["results"] for stage in item["matched_stages"])
            self.assertTrue(all(any(s["stage_kind"] == "base" for s in item["stages"]) for item in page["results"]))
        self.assertEqual(set(matched), {s["stage_id"] for s in extensions})

    def test_real_homographs_retain_all_fixed_identities(self):
        forms = defaultdict(list)
        for word in self.data.words:
            forms[word["written_form_base"]].append(word)
        duplicate_forms = {form: rows for form, rows in forms.items() if len(rows) > 1}
        self.assertEqual(len(duplicate_forms), 99)
        self.assertEqual(sum(map(len, duplicate_forms.values())), 203)
        form, records = next(iter(duplicate_forms.items()))
        result = self.data.word(form, limit=100)
        self.assertEqual({r["word"]["word_key"] for r in result["results"]}, {w["word_key"] for w in records})

    def test_real_relation_text_and_adjudications_are_unchanged(self):
        note = self.data.tables["source_notes"][0]
        word = self.data.word_index[note["word_key"]]
        result = self.data.word(word["written_form"], limit=100)
        item = next(r for r in result["results"] if r["word"]["word_key"] == word["word_key"])
        self.assertEqual(item["relations"], self.data.by_word["relations"][word["word_key"]])
        self.assertIn(note, item["source_notes"])
        disposition = self.data.tables["classification_dispositions"][0]
        self.assertIn(disposition, self.data.by_word["classification_dispositions"][disposition["word_key"]])
        self.assertTrue(all(r["current_research_state"] == "accepted_local_research" for r in item["relations"]))

    def test_real_source_differences_are_exposed_not_adopted(self):
        self.assertTrue(self.data.tables["source_differences"], "real source comparison records are required")
        diff = next(d for d in self.data.tables["source_differences"] if d["local_word_key"] is not None)
        word = self.data.word_index[diff["local_word_key"]]
        result = self.data.word(word["written_form"], limit=100)
        item = next(r for r in result["results"] if r["word"]["word_key"] == word["word_key"])
        self.assertIn(diff, item["source_differences"])
        self.assertEqual(diff["adoption_state"], "observed_not_adopted")
        self.assertEqual(item["word"]["source_snapshot_id"], result["source_snapshot_id"])


if __name__ == "__main__":
    unittest.main()
