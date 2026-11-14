"""``mlib.nodes.animCurve`` のテスト。

- キー操作の約束を固定する。
"""

import math
import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class _KeyCase(NamespaceCase):
    """translateX・rotateY にキーを打った transform を用意する。"""

    PREFIX = "mlibSpecKeyframe_"

    def setUp(self):
        super().setUp()
        self.units = (cmds.currentUnit(query=True, linear=True), cmds.currentUnit(query=True, angle=True))
        self.tangents = cmds.keyTangent(query=True, g=True, inTangentType=True, outTangentType=True)
        self.time = (cmds.currentUnit(query=True, time=True), cmds.currentTime(query=True))
        self.node = mlib.getNode(self.make("transform", "node"))
        self.name_ = self.node.getFullName()
        for time, value in ((1, 0.0), (5, 2.0), (10, 4.0)):
            cmds.setKeyframe(self.name_, attribute="translateX", time=time, value=value)
        cmds.setKeyframe(self.name_, attribute="rotateY", time=1, value=90.0)
        self.curve = self.node.getPlug("tx").getAnimCurve()
        selected = cmds.keyframe(query=True, selected=True, name=True)
        if selected:
            cmds.selectKey(selected, clear=True)

    def tearDown(self):
        cmds.currentUnit(linear=self.units[0], angle=self.units[1])
        cmds.keyTangent(g=True, inTangentType=self.tangents[0], outTangentType=self.tangents[1])
        cmds.currentUnit(time=self.time[0])
        cmds.currentTime(self.time[1])
        super().tearDown()

    def times(self, curve=None):
        return cmds.keyframe((curve or self.curve).getFullName(), query=True, timeChange=True) or []

    def values(self, curve=None):
        return cmds.keyframe((curve or self.curve).getFullName(), query=True, valueChange=True) or []


class AnimCurveEditTest(_KeyCase):
    """AnimCurve の moveKey・scaleKey・replaceKeys・removeKey(keepCurve)・setKey の接線の既定。"""

    def test_move_key_ranges(self):
        """index(単数・並び)・time(時刻・範囲)で絞り、省略は全キー。index と time の同時指定は TypeError。"""
        self.curve.moveKey(timeOffset=1)
        self.assertEqual(self.times(), [2.0, 6.0, 11.0])
        self.curve.moveKey(0, valueOffset=1)
        self.assertEqual(self.values(), [1.0, 2.0, 4.0])
        self.curve.moveKey([1, 2], timeOffset=2)
        self.assertEqual(self.times(), [2.0, 8.0, 13.0])
        self.curve.moveKey(time=(7, 20), timeOffset=-1, valueOffset=1)
        self.assertEqual(self.times(), [2.0, 7.0, 12.0])
        self.assertEqual(self.values(), [1.0, 3.0, 5.0])
        self.curve.moveKey(time=(100, 200), timeOffset=5)
        self.assertEqual(self.times(), [2.0, 7.0, 12.0])
        with self.assertRaises(TypeError):
            self.curve.moveKey(0, time=2, timeOffset=1)
        with self.assertRaises(IndexError):
            self.curve.moveKey(5, timeOffset=1)
        self.flushUndo()
        self.curve.moveKey(timeOffset=1, valueOffset=1)
        self.assertUndoesInOneStep(lambda: self.assertEqual(self.times(), [2.0, 7.0, 12.0]), lambda: self.assertEqual(self.times(), [3.0, 8.0, 13.0]))

    def test_move_key_seconds_and_degrees(self):
        """timeUnit="sec" は秒、角度の valueOffset は度(unit="rad" でラジアン)。"""
        cmds.currentUnit(time="film")
        self.curve.moveKey(timeOffset=1, timeUnit="sec")
        self.assertEqual(self.times(), [25.0, 29.0, 34.0])
        rotate = self.node.getPlug("ry").getAnimCurve()
        rotate.moveKey(valueOffset=math.pi, unit="rad")
        self.assertAlmostEqual(self.values(rotate)[0], 270.0)

    def test_scale_key_ranges(self):
        """scaleKey と mirror も index・time で絞れる。"""
        self.curve.scaleKey(1, 2, valuePivot=0, index=[1, 2])
        self.assertEqual(self.values(), [0.0, 4.0, 8.0])
        self.curve.scaleKey(2, 1, inputPivot=5, time=(5, 10))
        self.assertSequenceAlmostEqual(self.times(), [1.0, 5.0, 15.0], places=5)
        self.curve.mirror(value=True, valuePivot=4, index=1)
        self.assertEqual(self.values(), [0.0, 4.0, 8.0])
        self.curve.mirror(value=True, valuePivot=0, index=0)
        self.assertEqual(self.values(), [0.0, 4.0, 8.0])
        with self.assertRaises(TypeError):
            self.curve.scaleKey(2, index=0, time=1)
        with self.assertRaises(ValueError):
            self.curve.scaleKey(0, time=(1, 5))

    def test_remove_key_keep_curve(self):
        """既定(keepCurve=True)は全キーを消してもカーブと接続が残り、False は Maya と同じく消える。"""
        name = self.curve.getFullName()
        self.flushUndo()
        self.curve.removeKey([0, 1, 2])
        self.assertTrue(cmds.objExists(name))
        self.assertEqual(self.curve.getKeyCount(), 0)
        self.assertEqual(self.node.getPlug("tx").getAnimCurve(), self.curve)
        self.assertFalse(cmds.lockNode(name, query=True, lock=True)[0])
        cmds.undo()
        self.assertEqual(self.times(), [1.0, 5.0, 10.0])
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
        cmds.redo()
        self.assertEqual(self.curve.getKeyCount(), 0)
        cmds.undo()
        # すでにロックしていたカーブはロックを保つ。
        cmds.lockNode(name, lock=True)
        self.curve.removeKey(time=(0, 20))
        self.assertTrue(cmds.objExists(name))
        self.assertTrue(cmds.lockNode(name, query=True, lock=True)[0])
        cmds.undo()
        cmds.lockNode(name, lock=False)
        self.curve.removeKey(time=(0, 20), keepCurve=False)
        self.assertFalse(cmds.objExists(name))
        cmds.undo()
        self.assertTrue(cmds.objExists(name))
        with self.assertRaises(TypeError):
            self.curve.removeKey(0, keepCurve=1)

    def test_remove_key_fast(self):
        """fast は Undo に残さず、keepCurve=False で空になったカーブを削除する。"""
        free = mlib.createNode("animCurveTL", name=self.name("free"))
        free.setKey(1, 1).setKey(2, 2)
        self.flushUndo()
        free.removeKey([0, 1], fast=True)
        self.assertTrue(free.isValid())
        self.assertEqual(free.getKeyCount(), 0)
        free.setKey(1, 1, fast=True)
        free.removeKey(0, keepCurve=False, fast=True)
        self.assertFalse(free.isValid())
        self.assertUndoEmpty()

    def test_replace_keys(self):
        """replaceKeys はカーブと接続を残して全キーを置き換え、Undo 1 回で戻る。不正な要素では何も変えない。"""
        self.flushUndo()
        self.curve.replaceKeys([(2, 1.0), (4, 3.0, "linear", "step"), (4, 5.0)])
        self.assertUndoesInOneStep(
            lambda: self.assertEqual(self.times(), [1.0, 5.0, 10.0]), lambda: self.assertEqual((self.times(), self.values()), ([2.0, 4.0], [1.0, 5.0]))
        )
        cmds.redo()
        self.assertEqual(self.node.getPlug("tx").getAnimCurve(), self.curve)
        self.assertEqual(self.curve.getTangent(1)["inTangentType"], "linear")
        cmds.currentTime(3)
        self.assertAlmostEqual(cmds.getAttr(self.name_ + ".tx"), self.curve.evaluate(3))
        before = (self.times(), self.values())
        for keys in ([(1, 2, "linear")], [(1, float("nan"))], [(1, 2, "bogus", "linear")], ["ab"]):
            with self.subTest(keys=keys):
                with self.assertRaises((TypeError, ValueError)):
                    self.curve.replaceKeys(keys)
                self.assertEqual((self.times(), self.values()), before)
        self.curve.replaceKeys([])
        self.assertTrue(self.curve.isValid())
        self.assertEqual(self.curve.getKeyCount(), 0)

    def test_set_key_default_tangents(self):
        """接線型を省くと、既存のキーは接線型を保ち、新しいキーは Maya の設定(keyTangent -g)に従う。"""
        cmds.keyTangent(g=True, inTangentType="flat", outTangentType="step")
        for fast in (False, True):
            with self.subTest(fast=fast):
                curve = mlib.createNode("animCurveTL", name=self.name("tangent#"))
                curve.setKey(1, 1, fast=fast)
                tangent = curve.getTangent(0)
                self.assertEqual((tangent["inTangentType"], tangent["outTangentType"]), ("flat", "step"))
                curve.setTangent(0, inTangentType="linear", outTangentType="linear")
                curve.setKey(1, 5, fast=fast)
                tangent = curve.getTangent(0)
                self.assertEqual((tangent["inTangentType"], tangent["outTangentType"]), ("linear", "linear"))
                self.assertEqual(curve.getKeyValues(), [5.0])
                curve.setKey(2, 1, "spline", fast=fast)
                self.assertEqual(curve.getTangent(1)["inTangentType"], "spline")
                self.assertEqual(curve.getTangent(1)["outTangentType"], "step")

    def test_driven_plugs(self):
        """getDrivenPlugs は unitConversion を飛ばした出力先を返す。つながっていなければ空。"""
        self.assertEqual(self.curve.getDrivenPlugs(), [self.node.getPlug("tx")])
        rotate = self.node.getPlug("ry").getAnimCurve()
        self.assertEqual(rotate.getDrivenPlugs(), [self.node.getPlug("ry")])
        other = mlib.getNode(self.make("transform", "other"))
        cmds.connectAttr(self.curve.getFullName() + ".output", other.getFullName() + ".ty")
        self.assertEqual(set(self.curve.getDrivenPlugs()), {self.node.getPlug("tx"), other.getPlug("ty")})
        self.assertEqual(mlib.createNode("animCurveTL", name=self.name("lonely")).getDrivenPlugs(), [])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
