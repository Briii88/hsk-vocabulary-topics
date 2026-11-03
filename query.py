#!/usr/bin/env python3
"""Read and query the published vocabulary snapshot using only Python's standard library."""

import argparse
from collections import defaultdict
import copy
import hashlib
import json
from pathlib import Path
import sys

LEVELS = ("1", "2", "3", "4", "5", "6", "7-9")
TABLE_KEYS = {
    "words": "word_key", "stages": "stage_id", "relations": "relation_key",
    "themes": "theme_id", "taxonomy": "class_id", "source_notes": "note_id",
    "classification_dispositions": "issue_id", "source_differences": "comparison_id",
}
SOURCE_NOTICE = (
    "Word identities and source_sequence belong to source_snapshot_id. They do not map "
    "automatically to a current website sequence. Source differences are observed_not_adopted. "
    "Levels describe source base/extension stages, not every researched sense. "
    "accepted_local_research is a project research state, not official certification."
)


class DatasetError(ValueError):
    """The supplied public dataset is missing, inconsistent, or malformed."""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DatasetError("duplicate JSON key: " + key)
        result[key] = value
    return result


def _json(raw, label):
    try:
        return json.loads(raw, object_pairs_hook=_unique_object)
    except (ValueError, UnicodeError) as exc:
        raise DatasetError(label + ": invalid JSON: " + str(exc)) from exc


def _required(row, names, label):
    if not isinstance(row, dict) or not set(names).issubset(row):
        raise DatasetError(label + ": missing required fields")


def _page_args(limit, offset):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be an integer from 1 to 100")
    if type(offset) is not int or offset < 0:
        raise ValueError("offset must be a non-negative integer")


class Vocabulary:
    """Load one explicit data directory; never reads source files or network resources."""

    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir) if data_dir is not None else Path(__file__).resolve().parent / "data"
        self.manifest = _json((self.data_dir / "manifest.json").read_bytes(), "manifest.json")
        _required(self.manifest, ("files", "dataset_snapshot_version", "source_snapshot_id"), "manifest.json")
        if not isinstance(self.manifest["files"], list):
            raise DatasetError("manifest.files must be a list")
        manifest_files = {}
        for entry in self.manifest["files"]:
            _required(entry, ("path", "bytes", "sha256"), "manifest.files entry")
            if not isinstance(entry["path"], str) or entry["path"] in manifest_files:
                raise DatasetError("manifest has an invalid or duplicate file path")
            manifest_files[entry["path"]] = entry
        self.tables = {}
        self.by_id = {}
        for table, identity in TABLE_KEYS.items():
            name = table + ".jsonl"
            if name not in manifest_files:
                raise DatasetError("manifest is missing " + name)
            entry = manifest_files[name]
            raw = (self.data_dir / name).read_bytes()
            if len(raw) != entry["bytes"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
                raise DatasetError(name + ": bytes/hash differ from manifest; restore a consistent dataset")
            rows = [_json(line, "{} line {}".format(name, number))
                    for number, line in enumerate(raw.splitlines(), 1) if line.strip()]
            if entry.get("rows") != len(rows):
                raise DatasetError(name + ": row count differs from manifest")
            indexed = {}
            for row in rows:
                _required(row, (identity,), name)
                key = row[identity]
                if not isinstance(key, str) or not key or key in indexed:
                    raise DatasetError(name + ": invalid or duplicate " + identity)
                if row.get("dataset_snapshot_version") != self.manifest["dataset_snapshot_version"]:
                    raise DatasetError(name + ": inconsistent dataset snapshot version")
                source_key = "local_source_snapshot_id" if table == "source_differences" else "source_snapshot_id"
                if row.get(source_key) != self.manifest["source_snapshot_id"]:
                    raise DatasetError(name + ": inconsistent source snapshot identity")
                indexed[key] = row
            self.tables[table] = rows
            self.by_id[table] = indexed
        self._index()

    def _index(self):
        self.words = self.tables["words"]
        self.word_index = self.by_id["words"]
        self.by_word = {name: defaultdict(list) for name in
                        ("stages", "relations", "source_notes", "classification_dispositions", "source_differences")}
        for word in self.words:
            _required(word, ("vocab_id", "written_form", "written_form_base", "base_level_band"), "word")
            if word["base_level_band"] not in LEVELS:
                raise DatasetError("word has an invalid or split 7-9 level")
            if word["word_key"] != word["source_snapshot_id"] + "::" + word["vocab_id"]:
                raise DatasetError("word_key does not match its frozen source identity")
        for table, grouped in self.by_word.items():
            for row in self.tables[table]:
                key_field = "local_word_key" if table == "source_differences" else "word_key"
                _required(row, (key_field,), table)
                key = row[key_field]
                if table == "source_differences" and key is None:
                    continue
                if key not in self.word_index:
                    raise DatasetError(table + ": unknown word_key")
                grouped[key].append(row)
        for stage in self.tables["stages"]:
            _required(stage, ("stage_kind", "level_band"), "stage")
            if stage["stage_kind"] not in ("base", "extension") or stage["level_band"] not in LEVELS:
                raise DatasetError("stage has an invalid kind or split 7-9 level")
        for relation in self.tables["relations"]:
            _required(relation, ("current_research_state", "theme_id", "class_id", "relation_id"), "relation")
            if relation["current_research_state"] != "accepted_local_research":
                raise DatasetError("relations must contain the accepted current public research state")
            if relation["theme_id"] not in self.by_id["themes"] or relation["class_id"] not in self.by_id["taxonomy"]:
                raise DatasetError("relation has an unknown theme or class")
        for difference in self.tables["source_differences"]:
            if difference.get("adoption_state") != "observed_not_adopted":
                raise DatasetError("source differences must remain observed_not_adopted")

    def _base_response(self):
        return {
            "dataset_snapshot_version": self.manifest["dataset_snapshot_version"],
            "source_snapshot_id": self.manifest["source_snapshot_id"],
            "source_notice": SOURCE_NOTICE,
            "all_senses_complete": False,
        }

    def _resolve(self, selector, table, name_field):
        if selector is None:
            return None
        if type(selector) is not str or not selector.strip():
            raise ValueError("selector must be a non-empty string")
        if selector in self.by_id[table]:
            return selector
        identity = TABLE_KEYS[table]
        matches = [row[identity] for row in self.tables[table]
                   if selector == row[name_field] or selector in row.get("aliases", [])]
        if not matches:
            raise ValueError("unknown {}: {}".format("theme" if table == "themes" else "class", selector))
        if len(matches) != 1:
            raise ValueError("ambiguous class name/alias; use an exact class_id")
        return matches[0]

    def _item(self, word, relations, matched_stages=None):
        key = word["word_key"]
        return {
            "word": word,
            "stages": self.by_word["stages"][key],
            "matched_stages": matched_stages if matched_stages is not None else self.by_word["stages"][key],
            "relations": relations,
            "source_notes": self.by_word["source_notes"][key],
            "classification_dispositions": self.by_word["classification_dispositions"][key],
            "source_differences": self.by_word["source_differences"][key],
        }

    def _result(self, selected, limit, offset, **details):
        _page_args(limit, offset)
        page = selected[offset:offset + limit]
        return copy.deepcopy({
            **self._base_response(), **details,
            "status": "OK" if selected else "EMPTY_SELECTION",
            "total_matching_words": len(selected),
            "total_matching_relations": sum(len(item["relations"]) for item in selected),
            "total_matching_stages": sum(len(item["matched_stages"]) for item in selected),
            "returned_words": len(page), "limit": limit, "offset": offset,
            "results": page,
        })

    def word(self, text, *, limit=20, offset=0):
        if type(text) is not str or not text.strip():
            raise ValueError("word must be a non-empty string")
        selected = [self._item(word, self.by_word["relations"][word["word_key"]])
                    for word in self.words if text in (word["written_form"], word["written_form_base"])]
        return self._result(selected, limit, offset, query_word=text,
                            match_rule="exact written_form or written_form_base; identities are not deduplicated")

    def filter(self, *, level=None, mode="base", theme=None, class_id=None,
               all_words=False, limit=20, offset=0):
        if level is not None and (type(level) is not str or level not in LEVELS):
            raise ValueError("level must be 1–6 or the combined 7-9 band")
        if mode not in ("base", "cumulative", "extension"):
            raise ValueError("mode must be base, cumulative, or extension")
        if type(all_words) is not bool:
            raise ValueError("all_words must be a boolean")
        if mode == "cumulative" and level is None:
            raise ValueError("cumulative mode requires --level")
        wanted_theme = self._resolve(theme, "themes", "name")
        wanted_class = self._resolve(class_id, "taxonomy", "name")
        explicit = all_words or level is not None or theme is not None or class_id is not None
        selected = []
        if explicit:
            for word in self.words:
                stages = self.by_word["stages"][word["word_key"]]
                kind = "extension" if mode == "extension" else "base"
                matched = [stage for stage in stages if stage["stage_kind"] == kind
                           and (level is None or (LEVELS.index(stage["level_band"]) <= LEVELS.index(level)
                                if mode == "cumulative" else stage["level_band"] == level))]
                if not matched:
                    continue
                relations = [relation for relation in self.by_word["relations"][word["word_key"]]
                             if (wanted_theme is None or relation["theme_id"] == wanted_theme)
                             and (wanted_class is None or relation["class_id"] == wanted_class)]
                if not relations:
                    continue
                selected.append(self._item(word, relations, matched))
        return self._result(selected, limit, offset, explicit_selection=explicit,
                            mode=mode, level=level, theme_id=wanted_theme, class_id=wanted_class,
                            level_selection_rule="cumulative uses base stages only; all stages remain in each result")

    def related(self, text, *, scope="class", limit=20, offset=0):
        if type(text) is not str or not text.strip():
            raise ValueError("word must be a non-empty string")
        if scope not in ("class", "theme"):
            raise ValueError("related scope must be class or theme")
        seeds = [word for word in self.words if text in (word["written_form"], word["written_form_base"])]
        seed_keys = {word["word_key"] for word in seeds}
        field = "class_id" if scope == "class" else "theme_id"
        seed_relations = [relation for key in seed_keys for relation in self.by_word["relations"][key]]
        groups = {relation[field] for relation in seed_relations}
        selected = []
        for word in self.words:
            if word["word_key"] in seed_keys:
                continue
            relations = [relation for relation in self.by_word["relations"][word["word_key"]]
                         if relation[field] in groups]
            if relations:
                selected.append(self._item(word, relations))
        return self._result(selected, limit, offset, query_word=text, related_scope=scope,
                            relatedness_notice="Shared class/theme membership is not synonymy. The union of all matching seed identities is used; seed identities are excluded.",
                            seed_words=seeds, seed_relation_keys=sorted(r["relation_key"] for r in seed_relations),
                            matched_group_ids=sorted(groups))

    def themes(self, *, limit=100, offset=0):
        _page_args(limit, offset)
        rows = []
        for theme in self.tables["themes"]:
            relations = [r for r in self.tables["relations"] if r["theme_id"] == theme["theme_id"]]
            rows.append({**theme, "relation_count": len(relations),
                         "word_count": len({r["word_key"] for r in relations})})
        return copy.deepcopy({**self._base_response(), "total_themes": len(rows),
                              "limit": limit, "offset": offset,
                              "results": rows[offset:offset + limit]})


def parser():
    root = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    root.add_argument("--data-dir", help="directory containing manifest.json and the eight public JSONL tables")
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("word", "related", "filter", "themes"):
        sub = commands.add_parser(name, allow_abbrev=False)
        sub.add_argument("--data-dir", default=argparse.SUPPRESS)
        sub.add_argument("--limit", type=int, default=100 if name == "themes" else 20)
        sub.add_argument("--offset", type=int, default=0)
        if name in ("word", "related"):
            sub.add_argument("--word", required=True)
        if name == "related":
            sub.add_argument("--scope", choices=("class", "theme"), default="class")
        if name == "filter":
            sub.add_argument("--level", choices=LEVELS)
            sub.add_argument("--mode", choices=("base", "cumulative", "extension"), default="base")
            sub.add_argument("--theme", help="theme ID or exact name")
            sub.add_argument("--class", dest="class_id", help="class ID, exact name, or unique alias")
            sub.add_argument("--all", dest="all_words", action="store_true")
    return root


def main(argv=None):
    args = vars(parser().parse_args(argv))
    command = args.pop("command")
    data_dir = args.pop("data_dir")
    try:
        _page_args(args["limit"], args["offset"])
        dataset = Vocabulary(data_dir)
        if command == "word":
            result = dataset.word(args.pop("word"), **args)
        elif command == "related":
            result = dataset.related(args.pop("word"), **args)
        else:
            result = getattr(dataset, command)(**args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("error: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
