"""キーと接線の一括追加・入力検査・Undoを検証する。"""

import math
import sys
import unittest

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class AnimCurveAddKeysTest(NamespaceCase):
    def test_empty_curve_accepts_weighted_tangents_and_undo(self):
        """キー0件から接線ウェイトを反映し、1回のUndoで元の状態へ戻す。"""
        for suffix in ("TA", "UU"):
            with self.subTest(suffix=suffix):
                curve = mlib.createNode("animCurve" + suffix, name=self.name("empty" + suffix))
                self.assertEqual(curve.getKeyCount(), 0)
                self.assertFalse(curve.getPlug("weightedTangents").get())
                keys = [
                    {"input": 1, "value": 0.5, "inAngle": 0.2, "outAngle": -0.3, "inWeight": 1.5, "outWeight": 2.5, "lock": False, "weightLock": False},
                    {"input": 5, "value": 1.5, "inAngle": 0.4, "outAngle": -0.1, "inWeight": 2.0, "outWeight": 3.0, "lock": False, "weightLock": False},
                ]
                self.flushUndo()
                curve.addKeys(keys, unit="rad", weightedTangents=True)
                self.assertEqual(curve.getKeyInputs(), [1, 5])
                self.assertSequenceAlmostEqual(curve.getKeyValues(unit="rad"), [0.5, 1.5])
                for index, expected in enumerate(keys):
                    tangent = curve.getTangent(index, unit="rad")
                    self.assertTrue(tangent["weightedTangents"])
                    for field in ("inAngle", "outAngle", "inWeight", "outWeight"):
                        self.assertAlmostEqual(tangent[field], expected[field], places=5)
                cmds.undo()
                self.assertEqual(curve.getKeyCount(), 0)
                self.assertFalse(curve.getPlug("weightedTangents").get())
                cmds.redo()
                self.assertEqual(curve.getKeyCount(), 2)
                self.assertTrue(curve.getTangent(0)["weightedTangents"])
                self.assertAlmostEqual(curve.getTangent(0)["outWeight"], 2.5, places=5)

    def test_values_units_preserve_existing_and_undo_all_types(self):
        for suffix in ("TA", "TL", "TT", "TU", "UA", "UL", "UT", "UU"):
            with self.subTest(suffix=suffix):
                curve = mlib.createNode("animCurve" + suffix, name=self.name("curve" + suffix))
                curve.setKey(0, 7, timeUnit="sec", unit="rad")
                self.flushUndo()
                self.assertIsNone(curve.addKeys([{"input": 2, "value": 3}, {"input": 1, "value": 2}], timeUnit="sec", unit="rad"))
                self.assertSequenceAlmostEqual(curve.getKeyInputs(timeUnit="sec"), [0, 1, 2])
                self.assertSequenceAlmostEqual(curve.getKeyValues(timeUnit="sec", unit="rad"), [7, 2, 3])
                cmds.undo()
                self.assertEqual(curve.getKeyCount(), 1)
                self.assertAlmostEqual(curve.getKeyValues(unit="rad", timeUnit="sec")[0], 7)
                cmds.redo()
                self.assertEqual(curve.getKeyCount(), 3)

    def test_tangents_locks_and_collision(self):
        curve = mlib.createNode("animCurveTA", name=self.name("curve"))
        curve.setKey(0, 0)
        curve.setKey(10, 30)
        self.flushUndo()
        curve.addKeys(
            [
                {"input": 3, "value": 1, "inAngle": 0.2, "outAngle": 0.4, "inWeight": 1.5, "outWeight": 2.5, "lock": False, "weightLock": False},
                {"input": 7, "value": 2, "inTangentType": "linear", "outTangentType": "step", "lock": True},
            ],
            unit="rad",
            weightedTangents=True,
        )
        fixed = curve.getTangent(curve.findClosestIndex(3), unit="rad")
        self.assertAlmostEqual(fixed["inAngle"], 0.2, places=5)
        self.assertAlmostEqual(fixed["outAngle"], 0.4, places=5)
        self.assertAlmostEqual(fixed["inWeight"], 1.5, places=5)
        self.assertAlmostEqual(fixed["outWeight"], 2.5, places=5)
        self.assertFalse(fixed["lock"])
        self.assertFalse(fixed["weightLock"])
        self.assertTrue(fixed["weightedTangents"])
        self.assertEqual(curve.getTangent(curve.findClosestIndex(7))["outTangentType"], "step")
        cmds.undo()
        self.assertEqual(curve.getKeyInputs(), [0, 10])
        self.assertFalse(curve.getTangent(0)["weightedTangents"])
        with self.assertRaises(ValueError):
            curve.addKeys([{"input": 4, "value": 1}, {"input": 10, "value": 2}])
        self.assertEqual(curve.getKeyInputs(), [0, 10])
        curve.addKeys([{"input": 10, "value": math.pi}], unit="rad", replaceExisting=True)
        self.assertAlmostEqual(curve.getKeyValues()[1], 180)

    def test_all_records_are_validated_before_editing(self):
        curve = mlib.createNode("animCurveUU", name=self.name("curve"))
        for bad in (
            {"input": 2},
            {"input": 2, "value": 1, "typo": 1},
            {"input": 2, "value": float("nan")},
            {"input": 2, "value": 1, "inWeight": -1},
            {"input": 2, "value": 1, "outTangentType": "wrong"},
            {"input": 1, "value": 2},
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                curve.addKeys([{"input": 1, "value": 1}, bad])
            self.assertEqual(curve.getKeyCount(), 0)
        with self.assertRaises(TypeError):
            curve.addKeys([{"input": 1, "value": 2, "lock": 1}])
        self.assertIsNone(curve.addKeys([]))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
