"""Key Reducerの時間・許容値・接線・Undoを検証する。"""

import math
import sys
import unittest

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class AnimCurveReduceKeysTest(NamespaceCase):
    def setUp(self):
        super().setUp()
        self.time_unit = cmds.currentUnit(query=True, time=True)
        cmds.currentUnit(time="film")

    def tearDown(self):
        cmds.currentUnit(time=self.time_unit)
        super().tearDown()

    def test_reduce_all_time_output_types_and_exact_undo_redo(self):
        for kind in ("animCurveTA", "animCurveTL", "animCurveTU"):
            with self.subTest(kind=kind):
                curve = self._curve(kind)
                before = self._state(curve)
                samples = [curve.evaluate(index / 10.0, unit="rad", timeUnit="sec") for index in range(101)]
                self.flushUndo()
                self.assertIsNone(curve.reduceKeys(0.001, unit="rad", timeUnit="sec"))
                self.assertEqual(curve.getKeyCount(), 2)
                after = self._state(curve)
                self.assertSequenceAlmostEqual([curve.evaluate(index / 10.0, unit="rad", timeUnit="sec") for index in range(101)], samples)
                cmds.undo()
                self.assertEqual(self._state(curve), before)
                self.assertUndoEmpty()
                cmds.redo()
                self.assertEqual(self._state(curve), after)

    def test_absolute_precision_uses_internal_units_not_ui_units(self):
        for angle, linear, time in (("deg", "cm", "film"), ("rad", "m", "ntsc")):
            cmds.currentUnit(angle=angle, linear=linear, time=time)
            for kind in ("animCurveTA", "animCurveTL", "animCurveTU"):
                with self.subTest(kind=kind, angle=angle, linear=linear, time=time):
                    curve = self._curve(kind, values=(0, 1, 0))
                    curve.reduceKeys(0.5, unit="rad", timeUnit="sec")
                    self.assertEqual(curve.getKeyCount(), 3)
                    curve.reduceKeys(1.1, unit="rad", timeUnit="sec")
                    self.assertEqual(curve.getKeyCount(), 2)

    def test_default_degree_precision(self):
        angle_curve = self._curve("animCurveTA", values=(0, math.radians(10), 0))
        angle_curve.reduceKeys(5)
        self.assertEqual(angle_curve.getKeyCount(), 3)
        angle_curve.reduceKeys(11)
        self.assertEqual(angle_curve.getKeyCount(), 2)

    def test_range_keeps_outside_keys_and_uses_seconds(self):
        curve = self._curve()
        curve.reduceKeys(0.001, time=(3, 7), timeUnit="sec")
        self.assertEqual(curve.getKeyInputs(timeUnit="sec"), [0, 1, 2, 3, 7, 8, 9, 10])
        self.assertEqual(curve.getKeyValues(), [0, 1, 2, 3, 7, 8, 9, 10])

    def test_tangent_preservation_and_selected_keys_do_not_change_scope(self):
        curve = self._curve()
        curve.reduceKeys(1, preserveKeyTangent="linear")
        self.assertEqual(curve.getKeyCount(), 11)
        other = self._curve()
        cmds.selectKey(other.getName(full=True), time=(48, 120))
        try:
            curve.reduceKeys(1, precisionMode=1)
            self.assertEqual(curve.getKeyCount(), 2)
            self.assertEqual(other.getKeyCount(), 11)
        finally:
            cmds.selectKey(clear=True)

    def test_weighted_tangents_undo_and_step_preservation(self):
        curve = self._curve()
        cmds.keyTangent(curve.getName(full=True), weightedTangents=True)
        before = self._state(curve)
        self.flushUndo()
        curve.reduceKeys(0.001)
        cmds.undo()
        self.assertEqual(self._state(curve), before)
        step_curve = self._curve(values=(0, 1, 1, 2))
        cmds.keyTangent(step_curve.getName(full=True), outTangentType="step")
        step_curve.reduceKeys(100, preserveKeyTangent=("step", "stepnext"))
        self.assertEqual(step_curve.getKeyCount(), 4)

    def test_invalid_inputs_and_missing_output_do_not_write(self):
        curve = self._curve()
        before = self._state(curve)
        bad = (
            (-1, {}, ValueError),
            (float("inf"), {}, ValueError),
            (True, {}, TypeError),
            (1, {"precisionMode": True}, TypeError),
            (1, {"precisionMode": 2}, ValueError),
            (1, {"time": (3, 1)}, ValueError),
            (1, {"time": (1,)}, ValueError),
            (1, {"time": 3}, TypeError),
            (1, {"preserveKeyTangent": "missing"}, ValueError),
            (1, {"unit": "sec"}, ValueError),
            (1, {"timeUnit": "rad"}, ValueError),
        )
        self.flushUndo()
        for precision, flags, error in bad:
            with self.subTest(precision=precision, flags=flags), self.assertRaises(error):
                curve.reduceKeys(precision, **flags)
        self.assertEqual(self._state(curve), before)
        self.assertUndoEmpty()
        disconnected = self._curve(connected=False)
        cmds.connectAttr("time1.outTime", disconnected.getName(full=True) + ".input")
        self.flushUndo()
        with self.assertRaisesRegex(RuntimeError, "出力先"):
            disconnected.reduceKeys(1)
        self.assertEqual(disconnected.getKeyCount(), 11)
        self.assertUndoEmpty()

    def test_unitless_input_and_locked_keys_rejected(self):
        for kind in ("animCurveUU", "animCurveTT"):
            curve = self._curve(kind)
            self.flushUndo()
            with self.assertRaises(TypeError):
                curve.reduceKeys(1)
            self.assertEqual(curve.getKeyCount(), 11)
            self.assertUndoEmpty()
        curve = self._curve()
        cmds.setAttr(curve.getName(full=True) + ".keyTimeValue", lock=True)
        self.flushUndo()
        with self.assertRaises(RuntimeError):
            curve.reduceKeys(1)
        self.assertEqual(curve.getKeyCount(), 11)
        self.assertUndoEmpty()

    def _curve(self, kind="animCurveTL", values=None, connected=True):
        curve = mlib.createNode(kind, name=self.name("curve#"))
        if connected:
            target = self.make("transform", "target#")
            attribute = {"A": "rx", "L": "tx", "U": "sx", "T": "timeValue"}[kind[-1]]
            if attribute == "timeValue":
                cmds.addAttr(target, longName=attribute, attributeType="time")
            cmds.connectAttr(curve.getName(full=True) + ".output", target + "." + attribute)
        for index, value in enumerate(values if values is not None else range(11)):
            curve.addKey(index, value, unit="rad", timeUnit="sec", inTangentType="linear", outTangentType="linear")
        return curve

    @staticmethod
    def _state(curve):
        return (
            curve.getKeyInputs(timeUnit="sec"),
            curve.getKeyValues(unit="rad", timeUnit="sec"),
            [curve.getKeyframes(index).getTangent(unit="rad") for index in range(curve.getKeyCount())],
        )


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
