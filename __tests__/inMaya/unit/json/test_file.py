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

from mlib.json import Header, NodeRef, Snapshot
from mlib.json.file import _dump, _load
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
        written = _dump({"pivot": Translate(0, 12.5, 0), "name": "日本語"}, self.path, "mlib.test", 2)
        self.assertEqual(str(written), os.path.realpath(self.path))
        with open(self.path, encoding="utf-8") as stream:
            text = stream.read()
        self.assertIn("日本語", text)
        self.assertIn('\n  "header"', text)
        raw = std_json.loads(text)
        self.assertEqual(raw["header"]["format"], "mlib.test")
        self.assertEqual(raw["header"]["mlib"], mlib.__version__)
        self.assertEqual(raw["header"]["units"]["angle"], "deg")
        header, data = _load(self.path, "mlib.test", 2)
        self.assertIsInstance(header, Header)
        self.assertIs(type(data["pivot"]), Translate)
        self.assertEqual(data["name"], "日本語")
        self.assertEqual(list(os.listdir(self.folder)), ["data.json"])

    def test_format_and_version_mismatch(self):
        _dump({}, self.path, "mlib.test", 1)
        with self.assertRaisesRegex(ValueError, "の形式は"):
            _load(self.path, "mlib.other", 1)
        with self.assertRaisesRegex(ValueError, "のバージョン"):
            _load(self.path, "mlib.test", 2)
        with open(self.path, "w", encoding="utf-8") as stream:
            stream.write("{broken")
        with self.assertRaises(ValueError):
            _load(self.path, "mlib.test", 1)

    def test_failed_dump_keeps_existing_file(self):
        _dump({"a": 1}, self.path, "mlib.test", 1)
        with self.assertRaises(ValueError):
            _dump({"a": float("inf")}, self.path, "mlib.test", 1)
        self.assertEqual(_load(self.path, "mlib.test", 1)[1], {"a": 1})
        self.assertEqual(os.listdir(self.folder), ["data.json"])

    def test_failed_replace_leaves_no_temporary_file(self):
        """書き出し先がフォルダーで置き換えに失敗したとき、OSErrorにして一時ファイルを残さないことを確かめる。"""
        target = os.path.join(self.folder, "dir.json")
        os.mkdir(target)
        with self.assertRaises(OSError):
            _dump({"a": 1}, target, "mlib.test", 1)
        self.assertEqual(os.listdir(self.folder), ["dir.json"])

    def test_convert_time(self):
        cmds.currentUnit(time="ntsc")
        _dump({}, self.path, "mlib.test", 1)
        header, _data = _load(self.path, "mlib.test", 1)
        self.assertAlmostEqual(header.fps, 30.0)
        cmds.currentUnit(time="film")
        self.assertEqual(header._convert_time(30.0), 30.0)
        self.assertAlmostEqual(header._convert_time(30.0, timing="sec"), 24.0)
        with self.assertRaises(ValueError):
            header._convert_time(1.0, timing="seconds")

    def test_header_properties_and_invalid_arguments(self):
        """Headerの値・表記と、不正な引数の例外の型を確かめる。"""
        header = Header("mlib.test", 3, mlib="1.2.3", maya="2027", fps=30)
        self.assertEqual((header.format, header.version, header.mlib, header.maya, header.fps), ("mlib.test", 3, "1.2.3", "2027", 30.0))
        self.assertEqual(repr(header), "Header('mlib.test', 3, fps=30.0)")
        cmds.currentUnit(time="ntsc")
        self.assertAlmostEqual(Header("mlib.test", 1).fps, 30.0)
        cmds.currentUnit(time="film")
        self.assertAlmostEqual(Header("mlib.test", 1).fps, 24.0)
        for args, error in (
            ((1, 1), TypeError),
            (("", 1), ValueError),
            (("mlib.test", 1.0), TypeError),
            (("mlib.test", True), TypeError),
            (("mlib.test", 0), ValueError),
            (("mlib.test", 1, None, None, "24"), TypeError),
            (("mlib.test", 1, None, None, True), TypeError),
            (("mlib.test", 1, None, None, 0), ValueError),
            (("mlib.test", 1, None, None, -24.0), ValueError),
        ):
            with self.subTest(args=args), self.assertRaises(error):
                Header(*args[:2], **dict(zip(("mlib", "maya", "fps"), args[2:])))

    def test_invalid_files(self):
        """壊れたヘッダー・ファイルの形をValueErrorにし、dataがdictでなければTypeErrorにすることを確かめる。"""
        with self.assertRaises(TypeError):
            _dump([], self.path, "mlib.test", 1)
        _dump({}, self.path, "mlib.test", 1)
        with open(self.path, encoding="utf-8") as stream:
            good = std_json.load(stream)
        header = good["header"]
        units = header["units"]
        for label, payload in (
            ("list", []),
            ("extraKey", dict(good, extra=1)),
            ("dataNotDict", {"header": header, "data": []}),
            ("headerNotDict", {"header": [], "data": {}}),
            ("noUnits", {"header": {"format": "mlib.test", "version": 1}, "data": {}}),
            ("linear", {"header": dict(header, units=dict(units, linear="m")), "data": {}}),
            ("angle", {"header": dict(header, units=dict(units, angle="rad")), "data": {}}),
            ("time", {"header": dict(header, units=dict(units, time="second")), "data": {}}),
            ("noFormat", {"header": {key: value for key, value in header.items() if key != "format"}, "data": {}}),
            ("badVersion", {"header": dict(header, version="1"), "data": {}}),
        ):
            with open(self.path, "w", encoding="utf-8") as stream:
                std_json.dump(payload, stream)
            with self.subTest(label=label), self.assertRaises(ValueError):
                _load(self.path, "mlib.test", 1)


class _OffsetSnapshot(Snapshot):
    """テスト用: ノードの translateX を書く最小の種類。"""

    FORMAT = "mlib.test.offset"
    VERSION = 1

    @classmethod
    def capture(cls, nodes):
        return cls({"items": [{"node": NodeRef.capture(node)._to_data(), "value": cmds.getAttr(str(node) + ".tx")} for node in nodes]})

    def apply(self, *, nameMap=None, replace=None, namespaceMap=None, fail=False):
        return self._run_apply({"nameMap": nameMap, "replace": replace, "namespaceMap": namespaceMap}, {"fail": fail})

    def _validate(self, mapping, report, options):
        for item in self._data["items"]:
            ref = NodeRef._from_data(item["node"])
            if ref.resolve(mapping) is None:
                report._add_missing(ref._mapped_name(mapping))
            if item["value"] < 0:
                report._add_error("negative value")

    def _apply(self, mapping, report, options, fast):
        for item in self._data["items"]:
            node = NodeRef._from_data(item["node"]).resolve(mapping)
            if node is not None:
                cmds.setAttr(node.getName(full=True) + ".tx", item["value"])
        if options["fail"]:
            raise RuntimeError("fail on purpose")


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
