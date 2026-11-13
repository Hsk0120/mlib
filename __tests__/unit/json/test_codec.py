"""``mlib.json.codec`` のテスト。

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


class CodecTest(unittest.TestCase):
    """数学型の変換と往復。"""

    def test_round_trip_keeps_types(self):
        values = {
            "t": Translate(1.0, 2.5, -3.0),
            "s": Scale(1.0, 2.0, 3.0),
            "v": Vector(0.1, 0.2, 0.3),
            "q": Quaternion(0.0, 0.70710678, 0.0, 0.70710678),
            "r": EulerRotate.fromDegrees(10.0, 20.0, 30.0, "zxy"),
            "m": Matrix([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 5, 6, 7, 1]),
            "list": [1, "a", None, True, [Vector(1, 0, 0)]],
        }
        encoded = encode(values)
        self.assertEqual(encoded["t"], {"type": "Translate", "value": [1.0, 2.5, -3.0]})
        self.assertEqual(encoded["r"]["order"], "zxy")
        self.assertAlmostEqual(encoded["r"]["value"][1], 20.0)
        std_json.dumps(encoded, allow_nan=False)
        decoded = decode(std_json.loads(std_json.dumps(encoded)))
        self.assertIs(type(decoded["t"]), Translate)
        self.assertIs(type(decoded["s"]), Scale)
        self.assertIs(type(decoded["r"]), EulerRotate)
        self.assertEqual(decoded["r"].orderName, "zxy")
        self.assertTrue(decoded["r"].isEquivalent(values["r"], 1e-9))
        self.assertTrue(decoded["m"].isEquivalent(values["m"], 1e-12))
        self.assertTrue(decoded["q"].isEquivalent(values["q"], 1e-9))
        self.assertIs(type(decoded["list"][4][0]), Vector)

    def test_plain_dicts_with_type_key_stay_dicts(self):
        data = {"node": {"name": "a", "path": None, "type": "joint"}, "x": {"type": "Vector", "value": [1, 2]}}
        with self.assertRaises(ValueError):
            decode(data)
        self.assertEqual(decode(data["node"]), data["node"])

    def test_rejects_unsupported_values(self):
        for value in ({1: 2}, object(), float("nan")):
            with self.subTest(value=value), self.assertRaises((TypeError, ValueError)):
                encode(value)


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
