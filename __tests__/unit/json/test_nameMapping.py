"""``mlib.json.nameMapping`` のテスト。

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


class NameMappingTest(unittest.TestCase):
    """名前の変換の順序。"""

    def test_order_and_priority(self):
        mapping = NameMapping(nameMap={"arm_L_jnt": "leftArm"}, replace=[("_L_", "_R_")],
                              namespaceMap={"chrA": "chrB"})
        self.assertEqual(mapping.apply("chrA:arm_L_jnt"), "chrB:leftArm")
        self.assertEqual(mapping.apply("chrA:leg_L_jnt"), "chrB:leg_R_jnt")
        self.assertEqual(mapping.apply("leg_L_jnt"), "leg_R_jnt")
        self.assertEqual(mapping.applyPath("|chrA:root|chrA:arm_L_jnt"), "|chrB:root|chrB:leftArm")

    def test_namespaces(self):
        mapping = NameMapping(namespaceMap={"": "chrB", ":chrA:": "", "chrC": "x:y"})
        self.assertEqual(mapping.apply("root"), "chrB:root")
        self.assertEqual(mapping.apply("chrA:root"), "root")
        self.assertEqual(mapping.apply("chrC:sub:root"), "x:y:sub:root")
        self.assertTrue(NameMapping().isIdentity())
        self.assertEqual(NameMapping().apply("a:b"), "a:b")

    def test_invalid(self):
        for kwargs, error in (({"nameMap": []}, TypeError), ({"replace": "ab"}, TypeError),
                              ({"replace": [("a",)]}, ValueError), ({"replace": [("", "b")]}, ValueError),
                              ({"namespaceMap": {"a": 1}}, TypeError)):
            with self.subTest(kwargs=kwargs), self.assertRaises(error):
                NameMapping(**kwargs)


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


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
