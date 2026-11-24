"""``mlib.json.codec`` のテスト。

- mlib.json の基盤(codec・file・名前の対応付け・参照・Snapshot 基底)を確かめる。
"""

import json as std_json
import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.json import NodeRef, Snapshot
from mlib.json.codec import _decode, _encode
from mlib.maths import EulerRotate, Matrix, Quaternion, Scale, Translate, Vector


class CodecTest(unittest.TestCase):
    """数学型の変換と往復。"""

    def test_round_trip_keeps_types(self):
        values = {
            "t": Translate(1.0, 2.5, -3.0),
            "s": Scale(1.0, 2.0, 3.0),
            "v": Vector(0.1, 0.2, 0.3),
            "q": Quaternion(0.0, 0.70710678, 0.0, 0.70710678),
            "r": EulerRotate(10.0, 20.0, 30.0, "zxy", unit="deg"),
            "m": Matrix([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 5, 6, 7, 1]),
            "list": [1, "a", None, True, [Vector(1, 0, 0)]],
        }
        encoded = _encode(values)
        self.assertEqual(encoded["t"], {"type": "Translate", "value": [1.0, 2.5, -3.0]})
        self.assertEqual(encoded["r"]["order"], "zxy")
        self.assertAlmostEqual(encoded["r"]["value"][1], 20.0)
        std_json.dumps(encoded, allow_nan=False)
        decoded = _decode(std_json.loads(std_json.dumps(encoded)))
        self.assertIs(type(decoded["t"]), Translate)
        self.assertIs(type(decoded["s"]), Scale)
        self.assertIs(type(decoded["r"]), EulerRotate)
        self.assertEqual(decoded["r"].orderName, "zxy")
        self.assertTrue(decoded["r"].isEquivalent(values["r"], 1e-9))
        self.assertTrue(decoded["m"].isEquivalent(values["m"], 1e-12))
        self.assertTrue(decoded["q"].isEquivalent(values["q"], 1e-9))
        self.assertIs(type(decoded["list"][4][0]), Vector)

    def test_transformation_round_trip(self):
        """Transformation は成分の辞書で書き、既定値の補助の成分は省く。"""
        simple = mlib.Transformation(translate=(1, 2, 3), scale=(2, 2, 2))
        data = _encode(simple)
        self.assertEqual(data["type"], "Transformation")
        self.assertEqual(sorted(data["value"]), ["rotate", "rotateOrder", "scale", "shear", "translate"])
        self.assertEqual(data["value"]["rotateOrder"], "xyz")
        full = mlib.Transformation(
            rotateOrder=3,
            translate=(1, 2, 3),
            rotate=(0.1, 0.2, 0.3),
            scale=(2, 3, 4),
            shear=(0.1, 0.2, 0.3),
            rotateAxis=(0.05, 0.1, 0.15),
            rotatePivot=(1, 0, 2),
            rotatePivotTranslate=(0.1, 0.2, 0.3),
            scalePivot=(0, 1, 0),
            scalePivotTranslate=(0.3, 0.2, 0.1),
            jointOrient=(0.2, 0.1, 0.3),
            inverseScale=(2, 2, 4),
        )
        for value in (simple, full):
            with self.subTest(order=value.rotateOrder):
                restored = _decode(std_json.loads(std_json.dumps(_encode(value))))
                self.assertIs(type(restored), mlib.Transformation)
                self.assertEqual(restored.rotateOrder, value.rotateOrder)
                self.assertTrue(restored.isEquivalent(value, 1e-9))
                self.assertTrue(restored.matrix.isEquivalent(value.matrix, 1e-9))
        with self.assertRaises(ValueError):
            _decode({"type": "Transformation", "value": {"translate": [1, 2]}})
        with self.assertRaises(ValueError):
            _decode({"type": "Transformation", "value": {"unknown": [1, 2, 3]}})

    def test_plain_dicts_with_type_key_stay_dicts(self):
        data = {"node": {"name": "a", "path": None, "type": "joint"}, "x": {"type": "Vector", "value": [1, 2]}}
        with self.assertRaises(ValueError):
            _decode(data)
        self.assertEqual(_decode(data["node"]), data["node"])

    def test_rejects_unsupported_values(self):
        for value in ({1: 2}, object(), float("nan")):
            with self.subTest(value=value), self.assertRaises((TypeError, ValueError)):
                _encode(value)

    def test_rejects_non_finite_math_values(self):
        """数学型の成分にNaN・無限大があればValueErrorにすることを確かめる。"""
        for value in (Vector(float("inf"), 0, 0), Translate(0, float("nan"), 0), Quaternion(0, 0, 0, float("inf"))):
            with self.subTest(value=type(value).__name__), self.assertRaisesRegex(ValueError, "有限でない"):
                _encode({"value": [value]})


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
