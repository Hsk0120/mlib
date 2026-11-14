"""``mlib.common.keyframe`` のテスト。

- 入口(作成関数・objExists・Time・キーの追加/削除・Shapeの親変更・setPreferredAngle)の約束を固定する。
- キー操作の約束を固定する。
"""

import math
import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.common import Keyframe, Keyframes, Selection
from mlib.decorator import undoChunk


class _SpecCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、UI単位・選択の補助。"""

    PREFIX = "mlibSpecEntry_"

    def setUp(self):
        """UI単位・時刻を保存して名前空間を用意する。"""
        super().setUp()
        self.linear = cmds.currentUnit(query=True, linear=True)
        self.time = cmds.currentTime(query=True)
        self.range = (cmds.playbackOptions(query=True, minTime=True), cmds.playbackOptions(query=True, maxTime=True))

    def tearDown(self):
        """UI単位・時刻を戻す。"""
        cmds.currentUnit(linear=self.linear)
        cmds.playbackOptions(minTime=self.range[0], maxTime=self.range[1])
        cmds.currentTime(self.time)
        super().tearDown()

    def assert_one_undo(self, action):
        """actionを1回のUndoで戻せ、作ったノードが消えることを確かめる。"""
        before = set(cmds.ls(long=True))
        cmds.flushUndo()
        result = action()
        self.assertTrue(set(cmds.ls(long=True)) - before)
        cmds.undo()
        self.assertEqual(set(cmds.ls(long=True)), before)
        cmds.redo()
        return result


class KeyMethodsTest(_SpecCase):
    """Node.setKey・removeKey、Plug.removeKey、AnimCurve.removeKey(time=)。"""

    def test_set_and_remove_keys(self):
        """複数アトリビュートへのキー、範囲の削除、秒での指定、1回のUndoを確かめる。"""
        cmds.currentUnit(time="film")
        node = mlib.createNode("transform", name=self.name("keyed"), skipSelect=True)
        name = node.getFullName()
        cmds.flushUndo()
        node.setKey(["tx", "ry"], time=1)
        node.setKey(["tx", "ry"], time=1.0, timeUnit="sec", value=3)
        self.assertEqual(cmds.keyframe(name + ".tx", query=True, timeChange=True), [1.0, 24.0])
        cmds.undo()
        self.assertEqual(cmds.keyframe(name + ".tx", query=True, timeChange=True), [1.0])
        node.setKey(time=10)
        self.assertEqual(len(cmds.keyframe(name, query=True, name=True)), 10)
        node.setKey(["tx"], time=20)
        node.getPlug("tx").removeKey(time=(5, 15))
        self.assertEqual(cmds.keyframe(name + ".tx", query=True, timeChange=True), [1.0, 20.0])
        node.removeKey(["ry"], time=10)
        self.assertEqual(cmds.keyframe(name + ".ry", query=True, timeChange=True), [1.0])
        with self.assertRaises(TypeError):
            node.setKey(["tx"], attribute="ty")
        with self.assertRaises(ValueError):
            node.removeKey([], time=1)
        with self.assertRaises(ValueError):
            node.getPlug("tx").removeKey(time=(5, 1))
        curve = mlib.getNode(cmds.listConnections(name + ".tz", source=True)[0])
        curve.setKey(30, 1).setKey(40, 2)
        curve.removeKey(time=(25, 35), fast=True)
        self.assertEqual(curve.getKeyInputs(), [10.0, 40.0])
        curve.removeKey(time=(0.0, 1.0), timeUnit="sec")
        self.assertEqual(curve.getKeyInputs(), [40.0])
        with self.assertRaises(TypeError):
            curve.removeKey(0, time=40)
        with self.assertRaises(TypeError):
            curve.removeKey()


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


class KeyframeReferenceTest(_KeyCase):
    """Keyframe/Keyframes の取得・読取り・書込み。"""

    def test_read_matches_cmds(self):
        """getTime/getValue は cmds.keyframe の照会と一致し、repr・等価・ハッシュはカーブと番号で決まる。"""
        keys = self.curve.getKeyframes()
        self.assertIsInstance(keys, Keyframes)
        self.assertEqual(len(keys), 3)
        self.assertEqual([key.getTime() for key in keys], self.times())
        self.assertEqual(keys.getTimes(), self.times())
        self.assertEqual(keys.getValues(), self.values())
        key = self.curve.getKeyframe(1)
        self.assertIsInstance(key, Keyframe)
        self.assertEqual((key.getCurve(), key.getIndex()), (self.curve, 1))
        self.assertEqual(key, Keyframe(self.curve, 1))
        self.assertEqual(len({key, Keyframe(self.curve, 1), Keyframe(self.curve, 2)}), 2)
        self.assertIn(key, keys)
        self.assertIn("Keyframe(", repr(key))
        self.assertEqual(key.getTangent(), self.curve.getTangent(1))
        self.assertTrue(key.isValid())

    def test_invalid_input(self):
        """番号の範囲外は IndexError、AnimCurve 以外・Keyframe 以外は TypeError。"""
        for index in (-1, 3, True, 1.0):
            with self.subTest(index=index):
                with self.assertRaises(IndexError):
                    self.curve.getKeyframe(index)
        with self.assertRaises(IndexError):
            self.curve.getKeyframes([0, 9])
        with self.assertRaises(TypeError):
            Keyframe(self.node, 0)
        with self.assertRaises(TypeError):
            Keyframes([self.curve])

    def test_set_value_keeps_tangents_and_undoes_once(self):
        """setValue は接線型を保って値だけを変え、Undo 1 回で戻る。fast は Undo に残さない。"""
        self.curve.setTangent(1, inTangentType="linear", outTangentType="step")
        before = self.values()
        self.flushUndo()
        self.curve.getKeyframe(1).setValue(7.5)
        self.assertUndoesInOneStep(lambda: self.assertEqual(self.values(), before), lambda: self.assertEqual(self.values(), [0.0, 7.5, 4.0]))
        tangent = self.curve.getTangent(1)
        self.assertEqual((tangent["inTangentType"], tangent["outTangentType"]), ("linear", "step"))
        self.flushUndo()
        self.curve.getKeyframe(2).setValue(1.0, fast=True)
        self.assertEqual(self.values()[2], 1.0)
        self.assertUndoEmpty()

    def test_set_value_units(self):
        """角度は度(unit="rad" でラジアン)、距離は UI 単位によらず cm。"""
        cmds.currentUnit(linear="mm")
        self.curve.getKeyframe(0).setValue(1.5)
        self.assertAlmostEqual(self.values()[0], 15.0)
        self.assertAlmostEqual(self.curve.getKeyframe(0).getValue(), 1.5)
        rotate = self.node.getPlug("ry").getAnimCurve()
        rotate.getKeyframe(0).setValue(math.pi / 2, unit="rad")
        self.assertAlmostEqual(self.values(rotate)[0], 90.0)
        self.assertAlmostEqual(rotate.getKeyframe(0).getValue(unit="rad"), math.pi / 2)

    def test_keyframes_across_curves(self):
        """複数のカーブのキーをカーブごとにまとめ、setValue・move・remove を1回の Undo にする。"""
        rotate = self.node.getPlug("ry").getAnimCurve()
        keys = Keyframes([self.curve.getKeyframe(2), rotate.getKeyframe(0), self.curve.getKeyframe(0), self.curve.getKeyframe(0)])
        self.assertEqual(len(keys), 3)
        self.assertEqual(keys.getCurves(), [self.curve, rotate])
        self.assertEqual(keys.getIndices(self.curve), [0, 2])
        self.assertEqual([(curve, len(group)) for curve, group in keys.iterCurves()], [(self.curve, 2), (rotate, 1)])
        self.flushUndo()
        keys.setValue(3.0)
        self.assertUndoesInOneStep(lambda: self.assertEqual(self.values(), [0.0, 2.0, 4.0]), lambda: self.assertEqual(self.values(), [3.0, 2.0, 3.0]))
        self.flushUndo()
        keys.move(timeOffset=0, valueOffset=1)
        self.assertUndoesInOneStep(lambda: self.assertEqual(self.values(rotate), [90.0]), lambda: self.assertEqual(self.values(rotate), [91.0]))
        self.flushUndo()
        keys.remove()
        self.assertUndoesInOneStep(lambda: self.assertEqual(self.times(), [1.0, 5.0, 10.0]), lambda: self.assertEqual(self.times(), [5.0]))
        # keepCurve=True(既定)なので、全キーを消した rotateY のカーブも残る。
        self.assertTrue(rotate.isValid())

    def test_move_keeps_neighbor_order(self):
        """1つのキーを動かすと隣を越えない(Maya と同じ)。まとめて動かすキー同士は一緒に動く。"""
        self.curve.getKeyframe(0).move(timeOffset=20)
        self.assertLess(self.times()[0], 5.0)
        cmds.undo()
        self.curve.getKeyframes([1, 2]).move(timeOffset=3, valueOffset=-1)
        self.assertEqual(self.times(), [1.0, 8.0, 13.0])
        self.assertEqual(self.values(), [0.0, 1.0, 3.0])

    def test_driven_key_curve(self):
        """入力が時間でないカーブ(ドリブンキー)でも、時刻は入力値を指す。"""
        driven = mlib.createNode("animCurveUL", name=self.name("driven"))
        driven.setKey(0.25, 1.0).setKey(0.75, 3.0)
        key = driven.getKeyframe(1)
        self.assertEqual(key.getTime(), 0.75)
        key.move(timeOffset=0.1)
        self.assertAlmostEqual(key.getTime(), 0.85)
        key.setValue(2.0)
        self.assertEqual(driven.getKeyValues(), [1.0, 2.0])


class KeySelectionTest(_KeyCase):
    """Graph Editor・Dope Sheet のキーの選択。"""

    def test_select_and_query(self):
        """Keyframes.select の結果を Selection.getKeyframes・mlib.ls(selectedKeyframes=True) で取れる。"""
        self.assertEqual(len(Selection.getKeyframes()), 0)
        rotate = self.node.getPlug("ry").getAnimCurve()
        self.flushUndo()
        Keyframes([self.curve.getKeyframe(0), self.curve.getKeyframe(2), rotate.getKeyframe(0)]).select()
        self.assertEqual(sorted(cmds.keyframe(self.curve.getFullName(), query=True, selected=True, indexValue=True)), [0, 2])
        selected = Selection.getKeyframes()
        self.assertEqual(len(selected), 3)
        self.assertEqual(set(selected.getCurves()), {self.curve, rotate})
        self.assertEqual(selected.getIndices(self.curve), [0, 2])
        self.assertEqual(mlib.ls(selectedKeyframes=True), selected)
        self.curve.getKeyframe(1).select(add=True)
        self.assertEqual(Selection.getKeyframes().getIndices(self.curve), [0, 1, 2])
        self.curve.getKeyframe(1).select()
        self.assertEqual(len(Selection.getKeyframes()), 1)
        cmds.undo()
        self.assertEqual(Selection.getKeyframes().getIndices(self.curve), [0, 1, 2])
        Keyframes().select()
        self.assertEqual(len(Selection.getKeyframes()), 0)

    def test_ls_rejects_mixed_arguments(self):
        """selectedKeyframes=True は他の引数と併用できず、bool 以外は TypeError。False は通常の ls。"""
        for call in (
            lambda: mlib.ls(self.name_, selectedKeyframes=True),
            lambda: mlib.ls(selectedKeyframes=True, type="transform"),
            lambda: mlib.ls(selectedKeyframes=1),
        ):
            with self.assertRaises(TypeError):
                call()
        self.assertEqual(list(mlib.ls(self.name_, selectedKeyframes=False)), [self.node])


class PlugNodeKeyTest(_KeyCase):
    """Plug/Node の moveKey と setKey の値の単位。"""

    def test_plug_move_key(self):
        """Plug.moveKey は全キー(キーが1つでも)・時刻の範囲を動かし、値は get() と同じ単位。"""
        cmds.currentUnit(linear="mm")
        tx = self.node.getPlug("tx")
        self.flushUndo()
        tx.moveKey(timeOffset=2, valueOffset=1)
        self.assertUndoesInOneStep(lambda: self.assertEqual(self.times(), [1.0, 5.0, 10.0]), lambda: self.assertEqual(self.times(), [3.0, 7.0, 12.0]))
        cmds.redo()
        self.assertEqual(self.values(), [10.0, 30.0, 50.0])
        tx.moveKey(time=(5, 20), timeOffset=-1)
        self.assertEqual(self.times(), [3.0, 6.0, 11.0])
        ry = self.node.getPlug("ry")
        ry.moveKey(timeOffset=4, valueOffset=10)
        self.assertEqual(self.times(ry.getAnimCurve()), [5.0])
        self.assertAlmostEqual(self.values(ry.getAnimCurve())[0], 100.0)
        self.node.getPlug("tz").moveKey(timeOffset=1)
        for bad in ({"timeOffset": "1"}, {"valueOffset": True}):
            with self.assertRaises(TypeError):
                tx.moveKey(**bad)
        with self.assertRaises(ValueError):
            tx.moveKey(timeOffset=float("inf"))

    def test_node_move_key(self):
        """Node.moveKey は指定した(省略はキー可能な全)アトリビュートを、1回の Undo で動かす。"""
        rotate = self.node.getPlug("ry").getAnimCurve()
        self.flushUndo()
        self.node.moveKey(timeOffset=1, valueOffset=1)
        self.assertUndoesInOneStep(lambda: self.assertEqual(self.times(rotate), [1.0]), lambda: self.assertEqual(self.times(rotate), [2.0]))
        cmds.redo()
        self.assertEqual(self.values(), [1.0, 3.0, 5.0])
        self.assertAlmostEqual(self.values(rotate)[0], 91.0)
        self.node.moveKey(["tx"], time=(5, 20), timeOffset=1)
        self.assertEqual(self.times(), [2.0, 7.0, 12.0])
        self.assertEqual(self.times(rotate), [2.0])
        with self.assertRaises(ValueError):
            self.node.moveKey([], timeOffset=1)

    def test_node_set_key_units(self):
        """Node.setKey の value はアトリビュートごとに度・cm から換算し、uiUnits=True は UI 単位のまま。"""
        cmds.currentUnit(linear="mm")
        self.flushUndo()
        self.node.setKey(["tz", "rz"], time=3, value=2)
        self.assertUndoesInOneStep(
            lambda: self.assertFalse(cmds.keyframe(self.name_ + ".tz", query=True)),
            lambda: self.assertEqual(cmds.keyframe(self.name_ + ".tz", query=True, valueChange=True), [20.0]),
        )
        cmds.redo()
        self.assertAlmostEqual(cmds.keyframe(self.name_ + ".rz", query=True, valueChange=True)[0], 2.0)
        self.node.setKey(["tz"], time=4, value=2, uiUnits=True)
        self.assertEqual(cmds.keyframe(self.name_ + ".tz", query=True, valueChange=True), [20.0, 2.0])
        self.node.setKey(["rz"], time=4, value=math.pi, unit="rad")
        self.assertAlmostEqual(cmds.getAttr(self.name_ + ".rz", time=4), 180.0)
        self.node.setKey(["sx"], time=6)
        self.assertEqual(cmds.keyframe(self.name_ + ".sx", query=True, timeChange=True), [6.0])
        with self.assertRaises(ValueError):
            self.node.setKey(["tz"], time=5, value=1, unit="deg", uiUnits=True)
        with self.assertRaises(TypeError):
            self.node.setKey(["tz"], time=5, value=1, uiUnits=1)

    def test_get_default_matches_get(self):
        """getDefault は get() と同じ規則の数値。"""
        cmds.currentUnit(linear="mm", angle="rad")
        plug = self.node.addAttr("lin", attributeType="doubleLinear", defaultValue=3)
        self.assertAlmostEqual(plug.getDefault(), 3.0)
        self.assertAlmostEqual(plug.getDefault(), plug.get())
        self.assertAlmostEqual(plug.getDefault(uiUnits=True), 30.0)
        self.node.getPlug("rx").set(10)
        self.node.getPlug("rx").reset()
        self.assertEqual(self.node.getPlug("rx").get(), 0.0)


class WritablePlugsTest(_KeyCase):
    """getPlugs(writable=True) は今書ける(ロック・animCurve 以外の入力が無い)ものに絞る。"""

    def test_writable_filter(self):
        node = mlib.getNode(self.make("transform", "w"))
        name = node.getFullName()
        driver = mlib.getNode(self.make("transform", "driver"))
        cmds.setAttr(name + ".ty", lock=True)
        cmds.connectAttr(driver.getFullName() + ".tx", name + ".tz")
        cmds.setKeyframe(name, attribute="rx", time=1, value=5)
        cmds.connectAttr(driver.getFullName() + ".ty", name + ".sx")
        cmds.setAttr(name + ".scale", lock=True)
        keyable = [plug.getLongName() for plug in node.getPlugs(keyable=True)]
        writable = [plug.getLongName() for plug in node.getPlugs(keyable=True, writable=True)]
        self.assertEqual(writable, [plug for plug in keyable if plug not in ("translateY", "translateZ", "scaleX", "scaleY", "scaleZ")])
        self.assertIn("rotateX", writable)
        self.assertEqual(node.getPlugs(writable=False), node.getPlugs())
        with self.assertRaises(TypeError):
            node.getPlugs(writable=1)
        user = node.addAttr("free", attributeType="double", keyable=True)
        user.setLocked(True)
        self.assertNotIn(user, node.getPlugs(userDefined=True, writable=True))


class UndoChunkOpenCloseTest(NamespaceCase):
    """undoChunk の戻り値の open/close。"""

    PREFIX = "mlibSpecUndoOpen_"

    def test_open_close_spans_one_undo(self):
        """open から close までの変更が Undo 1 回にまとまり、二重の open・開かずの close は何もしない。"""
        node = self.make("transform", "n")
        self.flushUndo()
        chunk = undoChunk("drag")
        self.assertIs(chunk.open(), chunk)
        chunk.open()
        for value in (1, 2, 3):
            cmds.setAttr(node + ".tx", value)
        chunk.close()
        chunk.close()
        self.assertUndoesInOneStep(lambda: self.assertEqual(cmds.getAttr(node + ".tx"), 0.0), lambda: self.assertEqual(cmds.getAttr(node + ".tx"), 3.0))
        chunk.open()
        cmds.setAttr(node + ".ty", 5)
        chunk.close()
        cmds.undo()
        self.assertEqual(cmds.getAttr(node + ".ty"), 0.0)
        undoChunk("never").close()


if __name__ == "__main__":
    result = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if result.wasSuccessful() else 1)
