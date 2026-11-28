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
        self.name_ = self.node.getName(full=True)
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
        return cmds.keyframe((curve or self.curve).getName(full=True), query=True, timeChange=True) or []

    def values(self, curve=None):
        return cmds.keyframe((curve or self.curve).getName(full=True), query=True, valueChange=True) or []


class AnimCurveEditTest(_KeyCase):
    """AnimCurve のキーの移動(Keyframes.move)・scaleKey・replaceKeys・キーの削除(keepCurve)・addKey の接線の既定。"""

    def test_get_keyframes_by_time(self):
        """getKeyframes(time=) は時刻・範囲の中のキーを Keyframes で返す。timeUnit を受け、indices との同時指定は TypeError。"""
        self.assertEqual(self.curve.getKeyframes(time=(4, 20)).getIndices(self.curve), [1, 2])
        self.assertEqual(self.curve.getKeyframes(time=5).getIndices(self.curve), [1])
        self.assertEqual(len(self.curve.getKeyframes(time=(100, 200))), 0)
        seconds = mlib.common.units.convertTime(5, fromUnit=None, toUnit="sec")
        self.assertEqual(self.curve.getKeyframes(time=seconds, timeUnit="sec").getIndices(self.curve), [1])
        with self.assertRaises(TypeError):
            self.curve.getKeyframes(0, time=5)
        # AnimCurve の setKey・removeKey は Node と同じ意味(このノード自身のアトリビュート)。番号の操作は AnimCurve に置かない。
        for name in ("setKey", "removeKey", "moveKey"):
            with self.subTest(name=name):
                self.assertIs(getattr(type(self.curve), name), getattr(mlib.Node, name))
        for name in ("getTangent", "setTangent", "isBreakdown", "setBreakdown"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(type(self.curve), name))

    def test_move_key_ranges(self):
        """index(単数・並び)・time(時刻・範囲)で絞り、省略は全キー。index と time の同時指定は TypeError。"""
        self.curve.getKeyframes().move(timeOffset=1)
        self.assertEqual(self.times(), [2.0, 6.0, 11.0])
        self.curve.getKeyframes(0).move(valueOffset=1)
        self.assertEqual(self.values(), [1.0, 2.0, 4.0])
        self.curve.getKeyframes([1, 2]).move(timeOffset=2)
        self.assertEqual(self.times(), [2.0, 8.0, 13.0])
        self.curve.getKeyframes(time=(7, 20)).move(timeOffset=-1, valueOffset=1)
        self.assertEqual(self.times(), [2.0, 7.0, 12.0])
        self.assertEqual(self.values(), [1.0, 3.0, 5.0])
        self.curve.getKeyframes(time=(100, 200)).move(timeOffset=5)
        self.assertEqual(self.times(), [2.0, 7.0, 12.0])
        with self.assertRaises(TypeError):
            self.curve.getKeyframes(0, time=2).move(timeOffset=1)
        with self.assertRaises(IndexError):
            self.curve.getKeyframes(5).move(timeOffset=1)
        self.flushUndo()
        self.curve.getKeyframes().move(timeOffset=1, valueOffset=1)
        self.assertUndoesInOneStep(lambda: self.assertEqual(self.times(), [2.0, 7.0, 12.0]), lambda: self.assertEqual(self.times(), [3.0, 8.0, 13.0]))

    def test_move_key_seconds_and_degrees(self):
        """timeUnit="sec" は秒、角度の valueOffset は度(unit="rad" でラジアン)。"""
        cmds.currentUnit(time="film")
        self.curve.getKeyframes().move(timeOffset=1, timeUnit="sec")
        self.assertEqual(self.times(), [25.0, 29.0, 34.0])
        rotate = self.node.getPlug("ry").getAnimCurve()
        rotate.getKeyframes().move(valueOffset=math.pi, unit="rad")
        self.assertAlmostEqual(self.values(rotate)[0], 270.0)

    def test_scale_key_ranges(self):
        """scaleKey(倍率 -1 の反転を含む)も index・time で絞れる。"""
        self.curve.scaleKey(1, valueScale=2, valuePivot=0, index=[1, 2])
        self.assertEqual(self.values(), [0.0, 4.0, 8.0])
        self.curve.scaleKey(2, valueScale=1, inputPivot=5, time=(5, 10))
        self.assertSequenceAlmostEqual(self.times(), [1.0, 5.0, 15.0], places=5)
        self.curve.scaleKey(1, valueScale=-1, valuePivot=4, index=1)
        self.assertEqual(self.values(), [0.0, 4.0, 8.0])
        self.curve.scaleKey(valueScale=-1, valuePivot=0, index=0)
        self.assertEqual(self.values(), [0.0, 4.0, 8.0])
        # 基準から離れたキーは、値が基準の反対側へ移る。
        self.curve.scaleKey(valueScale=-1, valuePivot=4, index=2)
        self.assertEqual(self.values(), [0.0, 4.0, 0.0])
        self.curve.scaleKey(valueScale=-1, valuePivot=4, index=2)
        self.assertEqual(self.values(), [0.0, 4.0, 8.0])
        with self.assertRaises(TypeError):
            self.curve.scaleKey(2, index=0, time=1)
        with self.assertRaises(ValueError):
            self.curve.scaleKey(0, time=(1, 5))

    def test_remove_key_keep_curve(self):
        """既定(keepCurve=True)は全キーを消してもカーブと接続が残り、False は Maya と同じく消える。"""
        name = self.curve.getName(full=True)
        self.flushUndo()
        self.curve.getKeyframes([0, 1, 2]).delete()
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
        self.curve.getKeyframes(time=(0, 20)).delete()
        self.assertTrue(cmds.objExists(name))
        self.assertTrue(cmds.lockNode(name, query=True, lock=True)[0])
        cmds.undo()
        cmds.lockNode(name, lock=False)
        self.curve.getKeyframes(time=(0, 20)).delete(keepCurve=False)
        self.assertFalse(cmds.objExists(name))
        cmds.undo()
        self.assertTrue(cmds.objExists(name))
        with self.assertRaises(TypeError):
            self.curve.getKeyframes(0).delete(keepCurve=1)

    def test_remove_key_fast(self):
        """fast は Undo に残さず、keepCurve=False で空になったカーブを削除する。"""
        free = mlib.createNode("animCurveTL", name=self.name("free"))
        free.addKey(1, 1)
        free.addKey(2, 2)
        self.flushUndo()
        free.getKeyframes([0, 1]).delete(fast=True)
        self.assertTrue(free.isValid())
        self.assertEqual(free.getKeyCount(), 0)
        free.addKey(1, 1, fast=True)
        free.getKeyframes(0).delete(keepCurve=False, fast=True)
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
        self.assertEqual(self.curve.getKeyframes(1).getTangent()["inTangentType"], "linear")
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
                curve.addKey(1, 1, fast=fast)
                tangent = curve.getKeyframes(0).getTangent()
                self.assertEqual((tangent["inTangentType"], tangent["outTangentType"]), ("flat", "step"))
                curve.getKeyframes(0).setTangent(inTangentType="linear", outTangentType="linear")
                curve.addKey(1, 5, fast=fast)
                tangent = curve.getKeyframes(0).getTangent()
                self.assertEqual((tangent["inTangentType"], tangent["outTangentType"]), ("linear", "linear"))
                self.assertEqual(curve.getKeyValues(), [5.0])
                curve.addKey(2, 1, inTangentType="spline", fast=fast)
                self.assertEqual(curve.getKeyframes(1).getTangent()["inTangentType"], "spline")
                self.assertEqual(curve.getKeyframes(1).getTangent()["outTangentType"], "step")

    def test_driven_plugs(self):
        """getDrivenPlugs は unitConversion を飛ばした出力先を返す。つながっていなければ空。"""
        self.assertEqual(self.curve.getDrivenPlugs(), [self.node.getPlug("tx")])
        rotate = self.node.getPlug("ry").getAnimCurve()
        self.assertEqual(rotate.getDrivenPlugs(), [self.node.getPlug("ry")])
        other = mlib.getNode(self.make("transform", "other"))
        cmds.connectAttr(self.curve.getName(full=True) + ".output", other.getName(full=True) + ".ty")
        self.assertEqual(set(self.curve.getDrivenPlugs()), {self.node.getPlug("tx"), other.getPlug("ty")})
        self.assertEqual(mlib.createNode("animCurveTL", name=self.name("lonely")).getDrivenPlugs(), [])

    def test_remove_key_outside_keys_does_nothing(self):
        """キーの無い範囲の getKeyframes(time=...).delete() は、通常・fastとも何も消さずNoneを返す。"""
        for fast in (False, True):
            with self.subTest(fast=fast):
                self.assertIsNone(self.curve.getKeyframes(time=(20, 30)).delete(fast=fast))
                self.assertIsNone(self.curve.getKeyframes(time=3).delete(fast=fast))
                self.assertEqual(self.times(), [1.0, 5.0, 10.0])
                self.assertEqual(self.values(), [0.0, 2.0, 4.0])

    def test_time_range_inputs_rejected_before_change(self):
        """timeの組が2値でない・開始が終了より大きい場合は、getKeyframes(time=...) が何も変えずに例外。"""
        for label, operation, error in (
            ("remove three values", lambda: self.curve.getKeyframes(time=(1, 2, 3)).delete(), TypeError),
            ("remove reversed", lambda: self.curve.getKeyframes(time=(10, 1)).delete(), ValueError),
            ("move three values", lambda: self.curve.getKeyframes(time=[1, 2, 3]).move(timeOffset=1), TypeError),
            ("move reversed", lambda: self.curve.getKeyframes(time=(10, 1)).move(timeOffset=1), ValueError),
        ):
            with self.subTest(label=label):
                with self.assertRaises(error):
                    operation()
                self.assertEqual(self.times(), [1.0, 5.0, 10.0])

    def test_add_keys_and_set_tangent_reject_invalid_items(self):
        """addKeysの要素がdictでなければTypeError、setTangentのフラグが無いか知らない名前ならValueErrorで、何も変えない。"""
        tangents = cmds.keyTangent(self.curve.getName(full=True), query=True, index=(0, 0), inTangentType=True, outTangentType=True)
        for label, operation, error in (
            ("key tuple", lambda: self.curve.addKeys([(2, 1.0)]), TypeError),
            ("key mixed", lambda: self.curve.addKeys([{"input": 2, "value": 1.0}, 3]), TypeError),
            ("no flags", lambda: self.curve.getKeyframes(0).setTangent(), ValueError),
            ("unknown flag", lambda: self.curve.getKeyframes(0).setTangent(ott="linear"), ValueError),
            ("unknown flag fast", lambda: self.curve.getKeyframes(0).setTangent(fast=True, itt="linear"), ValueError),
        ):
            with self.subTest(label=label):
                with self.assertRaises(error):
                    operation()
                self.assertEqual(self.times(), [1.0, 5.0, 10.0])
        self.assertEqual(cmds.keyTangent(self.curve.getName(full=True), query=True, index=(0, 0), inTangentType=True, outTangentType=True), tangents)

    def test_reduce_keys_rejects_invalid_preserved_tangents(self):
        """reduceKeysのpreserveKeyTangentは文字列かその並びで、違う型はTypeError・知らない名前はValueError。"""
        for label, value, error in (
            ("int", 5, TypeError),
            ("item int", [1], TypeError),
            ("item None", ("linear", None), TypeError),
            ("name", ["curvy"], ValueError),
        ):
            with self.subTest(label=label):
                with self.assertRaises(error):
                    self.curve.reduceKeys(0.5, preserveKeyTangent=value)
                self.assertEqual(self.times(), [1.0, 5.0, 10.0])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
