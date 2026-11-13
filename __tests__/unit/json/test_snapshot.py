"""``mlib.json.snapshot`` のテスト。

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

from mlib.json import (
    ComponentRef,
    decode,
    dump,
    encode,
    Header,
    load,
    NameMapping,
    NodeRef,
    PlugRef,
    Snapshot,
    ValidationReport,
)
from mlib.maths import EulerRotate, Matrix, Quaternion, Scale, Translate, Vector
from support.namespaceCase import NamespaceCase


class _OffsetSnapshot(Snapshot):
    """テスト用: ノードの translateX を書く最小の種類。"""

    FORMAT = "mlib.test.offset"
    VERSION = 1

    @classmethod
    def capture(cls, nodes):
        return cls({"items": [{"node": NodeRef.capture(node).toData(),
                               "value": cmds.getAttr(str(node) + ".tx")} for node in nodes]})

    def apply(self, *, nameMap=None, replace=None, namespaceMap=None, fail=False):
        return self._run_apply({"nameMap": nameMap, "replace": replace, "namespaceMap": namespaceMap},
                               {"fail": fail})

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


class SnapshotBaseTest(NamespaceCase):
    """Snapshot 基底の保存・検査・適用・巻き戻し。"""

    PREFIX = "mlibSpecJsonSnap_"

    def setUp(self):
        super().setUp()
        self.a = cmds.createNode("transform", name=self.name("a"))
        self.b = cmds.createNode("transform", name=self.name("b"))
        cmds.setAttr(self.a + ".tx", 3.0)
        cmds.setAttr(self.b + ".tx", 4.0)
        self.folder = tempfile.mkdtemp(prefix="mlibJsonSnap")

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)
        super().tearDown()

    def test_save_load_apply(self):
        snap = _OffsetSnapshot.capture([self.a, self.b])
        self.assertIsNone(snap.header)
        path = snap.save(os.path.join(self.folder, "offset.json"))
        loaded = _OffsetSnapshot.load(path)
        self.assertIsInstance(loaded.header, Header)
        self.assertEqual(loaded.toData(), snap.toData())
        cmds.setAttr(self.a + ".tx", 0.0)
        cmds.delete(self.b)
        report = loaded.validate()
        self.assertTrue(report.valid)
        self.assertEqual(report.missing, [self.name("b")])
        self.assertEqual(cmds.getAttr(self.a + ".tx"), 0.0)
        cmds.flushUndo()
        result = loaded.apply()
        self.assertIsInstance(result, ValidationReport)
        self.assertEqual(cmds.getAttr(self.a + ".tx"), 3.0)
        cmds.undo()
        self.assertEqual(cmds.getAttr(self.a + ".tx"), 0.0)

    def test_errors_change_nothing_and_failure_rolls_back(self):
        cmds.setAttr(self.a + ".tx", -1.0)
        snap = _OffsetSnapshot.capture([self.a])
        cmds.setAttr(self.a + ".tx", 7.0)
        with self.assertRaises(ValueError):
            snap.apply()
        self.assertEqual(cmds.getAttr(self.a + ".tx"), 7.0)
        snap = _OffsetSnapshot.capture([self.b])
        cmds.setAttr(self.b + ".tx", 9.0)
        with self.assertRaises(RuntimeError):
            snap.apply(fail=True)
        self.assertEqual(cmds.getAttr(self.b + ".tx"), 9.0)

    def test_load_rejects_other_format(self):
        path = os.path.join(self.folder, "x.json")
        dump({"items": []}, path, "mlib.other", 1)
        with self.assertRaises(ValueError):
            _OffsetSnapshot.load(path)

    def test_data_is_copied(self):
        snap = _OffsetSnapshot({"items": [], "v": Vector(1, 2, 3)})
        data = snap.toData()
        data["v"].x = 99
        self.assertEqual(snap.toData()["v"].x, 1)
        with self.assertRaises(TypeError):
            _OffsetSnapshot([])
        with self.assertRaises(NotImplementedError):
            Snapshot.capture()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
