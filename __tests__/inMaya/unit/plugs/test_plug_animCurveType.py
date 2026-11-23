"""アニメーションカーブの出力型の選択を検証する。"""

import sys
import unittest

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class PlugAnimCurveTypeTest(NamespaceCase):
    def test_unit_types_and_no_scene_edits(self):
        node = mlib.getNode(cmds.createNode("transform", name=self.ns + ":node"))
        before = cmds.ls(long=True)
        for attr, suffix in (("tx", "L"), ("rx", "A"), ("sx", "U")):
            plug = node.getPlug(attr)
            self.assertEqual(plug.getAnimCurve(suitableType=True), "animCurveT" + suffix)
            self.assertEqual(plug.getAnimCurve(suitableType=True, timeInput=False), "animCurveU" + suffix)
        cmds.addAttr(node.getName(), longName="timeValue", attributeType="time")
        self.assertEqual(node.getPlug("timeValue").getAnimCurve(suitableType=True), "animCurveTT")
        self.assertEqual(node.getPlug("timeValue").getAnimCurve(suitableType=True, timeInput=False), "animCurveUT")
        self.assertEqual(cmds.ls(long=True), before)
        with self.assertRaises(TypeError):
            node.getPlug("tx").getAnimCurve(suitableType=True, timeInput=1)

    def test_suitable_type_is_not_the_connected_curve_type(self):
        """suitableType=Trueはカーブが無くても答え、つながっているカーブの型ではなくPlugに合う型を返す。カーブは作らない。"""
        node = mlib.getNode(cmds.createNode("transform", name=self.ns + ":suitable"))
        plug = node.getPlug("tx")
        self.assertIsNone(plug.getAnimCurve())
        self.assertEqual(plug.getAnimCurve(suitableType=True), "animCurveTL")
        self.assertEqual(plug.getAnimCurve(suitableType=True, timeInput=True), "animCurveTL")
        self.assertEqual(plug.getAnimCurve(suitableType=False), plug.getAnimCurve())
        self.assertFalse(cmds.listConnections(str(plug), source=True, destination=False))
        # 型の合わないカーブ(単位なし入力のanimCurveUU)をつないでも、答えはPlugに合う型のまま。
        curve = cmds.createNode("animCurveUU", name=self.ns + ":driven")
        cmds.connectAttr(curve + ".output", str(plug))
        self.assertEqual(plug.getAnimCurve().getType(), "animCurveUU")
        self.assertEqual(plug.getAnimCurve(suitableType=True), "animCurveTL")
        self.assertEqual(plug.getAnimCurve(suitableType=True, timeInput=False), "animCurveUL")
        before = cmds.ls(long=True)
        self.flushUndo()
        plug.getAnimCurve(suitableType=True)
        self.assertEqual(cmds.ls(long=True), before)
        self.assertUndoEmpty()

    def test_suitable_type_argument_errors(self):
        """timeInputはsuitableType=Trueのときだけ。layer・indirectとは同時に指定できない(TypeError)。"""
        node = mlib.getNode(cmds.createNode("transform", name=self.ns + ":errors"))
        plug = node.getPlug("tx")
        layer = "notResolvedLayer"
        for label, call in (
            ("timeInputWithoutSuitable", lambda: plug.getAnimCurve(timeInput=True)),
            ("timeInputFalseWithoutSuitable", lambda: plug.getAnimCurve(suitableType=False, timeInput=False)),
            ("indirect", lambda: plug.getAnimCurve(suitableType=True, indirect=True)),
            ("layer", lambda: plug.getAnimCurve(layer, suitableType=True)),
            ("suitableInt", lambda: plug.getAnimCurve(suitableType=1)),
            ("suitableNone", lambda: plug.getAnimCurve(suitableType=None)),
            ("timeInputStr", lambda: plug.getAnimCurve(suitableType=True, timeInput="yes")),
            ("positional", lambda: plug.getAnimCurve(None, False, True)),
        ):
            with self.subTest(case=label):
                with self.assertRaises(TypeError):
                    call()
        self.assertEqual(plug.getAnimCurve(suitableType=True, timeInput=None), "animCurveTL")
        self.assertEqual(plug.getAnimCurve(suitableType=True, indirect=False, layer=None), "animCurveTL")


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
