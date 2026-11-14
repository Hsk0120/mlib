"""``mlib.json.file`` のテスト。

- mlib.json の基盤(codec・file・名前の対応付け・参照・Snapshot 基底)を確かめる。
"""

import json as std_json
import os
import shutil
import sys
import tempfile
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.json import Header, NodeRef, Snapshot, dump, load
from mlib.maths import Translate


class FileTest(unittest.TestCase):
    """ヘッダー付きファイルの書き出しと読み込み。"""

    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="mlibJsonTest")
        self.path = os.path.join(self.folder, "data.json")
        self.time_unit = cmds.currentUnit(query=True, time=True)

    def tearDown(self):
        cmds.currentUnit(time=self.time_unit)
        shutil.rmtree(self.folder, ignore_errors=True)

    def test_dump_and_load(self):
        written = dump({"pivot": Translate(0, 12.5, 0), "name": "日本語"}, self.path, "mlib.test", 2)
        self.assertEqual(str(written), os.path.realpath(self.path))
        with open(self.path, encoding="utf-8") as stream:
            text = stream.read()
        self.assertIn("日本語", text)
        self.assertIn('\n  "header"', text)
        raw = std_json.loads(text)
        self.assertEqual(raw["header"]["format"], "mlib.test")
        self.assertEqual(raw["header"]["mlib"], mlib.__version__)
        self.assertEqual(raw["header"]["units"]["angle"], "deg")
        header, data = load(self.path, "mlib.test", 2)
        self.assertIsInstance(header, Header)
        self.assertIs(type(data["pivot"]), Translate)
        self.assertEqual(data["name"], "日本語")
        self.assertEqual(list(os.listdir(self.folder)), ["data.json"])

    def test_format_and_version_mismatch(self):
        dump({}, self.path, "mlib.test", 1)
        with self.assertRaisesRegex(ValueError, "format"):
            load(self.path, "mlib.other", 1)
        with self.assertRaisesRegex(ValueError, "version"):
            load(self.path, "mlib.test", 2)
        with open(self.path, "w", encoding="utf-8") as stream:
            stream.write("{broken")
        with self.assertRaises(ValueError):
            load(self.path, "mlib.test", 1)

    def test_failed_dump_keeps_existing_file(self):
        dump({"a": 1}, self.path, "mlib.test", 1)
        with self.assertRaises(ValueError):
            dump({"a": float("inf")}, self.path, "mlib.test", 1)
        self.assertEqual(load(self.path, "mlib.test", 1)[1], {"a": 1})
        self.assertEqual(os.listdir(self.folder), ["data.json"])

    def test_convert_time(self):
        cmds.currentUnit(time="ntsc")
        dump({}, self.path, "mlib.test", 1)
        header, _data = load(self.path, "mlib.test", 1)
        self.assertAlmostEqual(header.fps, 30.0)
        cmds.currentUnit(time="film")
        self.assertEqual(header.convertTime(30.0), 30.0)
        self.assertAlmostEqual(header.convertTime(30.0, timing="second"), 24.0)
        with self.assertRaises(ValueError):
            header.convertTime(1.0, timing="seconds")


class _OffsetSnapshot(Snapshot):
    """テスト用: ノードの translateX を書く最小の種類。"""

    FORMAT = "mlib.test.offset"
    VERSION = 1

    @classmethod
    def capture(cls, nodes):
        return cls({"items": [{"node": NodeRef.capture(node).toData(), "value": cmds.getAttr(str(node) + ".tx")} for node in nodes]})

    def apply(self, *, nameMap=None, replace=None, namespaceMap=None, fail=False):
        return self._run_apply({"nameMap": nameMap, "replace": replace, "namespaceMap": namespaceMap}, {"fail": fail})

    def _validate(self, mapping, report, options):
        for item in self._data["items"]:
            ref = NodeRef.fromData(item["node"])
            if ref.resolve(mapping) is None:
                report.addMissing(ref.mappedName(mapping))
            if item["value"] < 0:
                report.addError("negative value")

    def _apply(self, mapping, report, options, fast):
        for item in self._data["items"]:
            node = NodeRef.fromData(item["node"]).resolve(mapping)
            if node is not None:
                cmds.setAttr(node.getFullName() + ".tx", item["value"])
        if options["fail"]:
            raise RuntimeError("fail on purpose")


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
