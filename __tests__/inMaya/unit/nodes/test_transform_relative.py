"""``mlib.nodes.transform`` のテスト。

- Transform・DagNode・Joint・IkHandle のメソッドと createGroup を確かめる。
"""

import math
import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class _Case(NamespaceCase):
    """ノードを作る補助。"""

    PREFIX = "mlibDagAdd_"

    def transform(self, text="node#", parent=None):
        """transform を作り、ラッパーを返す。"""
        return mlib.getNode(cmds.ls(self.make("transform", text, parent), long=True)[0])

    def chain(self):
        """3つの joint の連鎖を作り、名前のリストを返す。"""
        cmds.select(clear=True)
        names = [cmds.joint(name=self.name(f"j{i}"), position=position) for i, position in enumerate(((0, 0, 0), (0, 2, 1), (0, 4, 0)))]
        cmds.select(clear=True)
        return [cmds.ls(name, long=True)[0] for name in names]

    def assertRaisesNoChange(self, error, read, call):
        """call が error を送出し、read の値を変えないことを確かめる。"""
        before = read()
        with self.assertRaises(error):
            call()
        self.assertEqual(read(), before)


class RelativeTransformTest(_Case):
    """translateBy・rotateBy・scaleBy。"""

    def setUp(self):
        super().setUp()
        self.parent = self.transform("parent#")
        cmds.setAttr(self.parent.getFullName() + ".r", 10, 40, -20)
        # 親の非一様なスケールはワールドのマトリクスにシアーを生み、ワールド軸の回転が定まらないため一様にする。
        cmds.setAttr(self.parent.getFullName() + ".s", 2, 2, 2)
        self.node = self.transform("node#", self.parent.getFullName())
        self.reference = self.transform("reference#", self.parent.getFullName())
        for node in (self.node, self.reference):
            cmds.setAttr(node.getFullName() + ".t", 1, 2, 3)
            cmds.setAttr(node.getFullName() + ".r", 10, 20, 30)
            cmds.setAttr(node.getFullName() + ".ro", 2)
            cmds.setAttr(node.getFullName() + ".s", 1, 2, 3)

    def values(self, node, attribute):
        return cmds.getAttr(node.getFullName() + "." + attribute)[0]

    def test_translate_by_matches_cmds_move(self):
        """translateBy は親の空間・ワールドの軸で cmds.move(relative) と同じ translate になる。"""
        ref = self.reference.getFullName()
        self.assertIs(self.node.translateBy((1, -2, 0.5)), self.node)
        cmds.move(1, -2, 0.5, ref, relative=True, localSpace=True)
        self.assertSequenceAlmostEqual(self.values(self.node, "t"), self.values(self.reference, "t"))
        self.node.translateBy((3, 0, 1), ws=True)
        cmds.move(3, 0, 1, ref, relative=True, worldSpace=True)
        self.assertSequenceAlmostEqual(self.values(self.node, "t"), self.values(self.reference, "t"))

    def test_rotate_by_matches_cmds_rotate(self):
        """rotateBy はローカル軸・ワールドの軸で cmds.rotate(relative) と同じ向きになる(rotateOrder=zxy)。"""
        ref = self.reference.getFullName()
        self.node.rotateBy((5, 15, 25))
        cmds.rotate(5, 15, 25, ref, relative=True, objectSpace=True)
        self.assertSequenceAlmostEqual(self.values(self.node, "r"), self.values(self.reference, "r"), places=6)
        self.node.rotateBy((math.radians(20), 0, math.radians(-10)), worldSpace=True, unit="rad")
        cmds.rotate(20, 0, -10, ref, relative=True, worldSpace=True)
        self.assertSequenceAlmostEqual(
            cmds.xform(self.node.getFullName(), query=True, matrix=True, worldSpace=True), cmds.xform(ref, query=True, matrix=True, worldSpace=True), places=6
        )

    def test_rotate_by_accumulates(self):
        """90度ずつ4回回すと rotate は360度へ進む(等価解を今の値の近くに選ぶ)。"""
        node = self.transform("free#")
        for _ in range(4):
            node.rotateBy((0, 0, 90))
        self.assertAlmostEqual(cmds.getAttr(node.getFullName() + ".rz"), 360.0, places=6)
        quarter = om2.MEulerRotation(0.0, math.radians(90), 0.0)
        node.rotateBy(quarter)
        self.assertAlmostEqual(cmds.getAttr(node.getFullName() + ".ry"), 90.0, places=6)

    def test_scale_by(self):
        """scaleBy は scale へ倍率を掛ける。数値1つは XYZ 共通。"""
        self.node.scaleBy((2, 0.5, 1))
        self.assertSequenceAlmostEqual(self.values(self.node, "s"), (2, 1, 3))
        self.node.scaleBy(3)
        self.assertSequenceAlmostEqual(self.values(self.node, "s"), (6, 3, 9))

    def test_undo_one_step(self):
        """各メソッドは Undo 1 回で戻る。"""
        name = self.node.getFullName()
        before = cmds.xform(name, query=True, matrix=True)
        for label, call in (
            ("translateBy", lambda: self.node.translateBy((1, 2, 3), ws=True)),
            ("rotateBy", lambda: self.node.rotateBy((10, 0, 5), ws=True)),
            ("scaleBy", lambda: self.node.scaleBy((2, 2, 2))),
        ):
            with self.subTest(label):
                self.flushUndo()
                call()
                self.assertUndoesInOneStep(
                    lambda: self.assertSequenceAlmostEqual(cmds.xform(name, query=True, matrix=True), before),
                    lambda: self.assertNotEqual(cmds.xform(name, query=True, matrix=True), before),
                )

    def test_invalid_input(self):
        """不正な入力・ロック・削除済みノードは例外で、値を変えない。"""
        name = self.node.getFullName()

        def read():
            return cmds.xform(name, query=True, matrix=True)

        for label, error, call in (
            ("translate 2", ValueError, lambda: self.node.translateBy((1, 2))),
            ("translate str", TypeError, lambda: self.node.translateBy("abc")),
            ("translate nan", ValueError, lambda: self.node.translateBy((1, float("nan"), 0))),
            ("translate ws twice", TypeError, lambda: self.node.translateBy((1, 0, 0), True, ws=True)),
            ("translate ws int", TypeError, lambda: self.node.translateBy((1, 0, 0), worldSpace=1)),
            ("rotate unit", ValueError, lambda: self.node.rotateBy((1, 0, 0), unit="turn")),
            ("rotate 4", ValueError, lambda: self.node.rotateBy((1, 0, 0, 0))),
            ("scale bool", TypeError, lambda: self.node.scaleBy(True)),
            ("scale inf", ValueError, lambda: self.node.scaleBy(float("inf"))),
        ):
            with self.subTest(label):
                self.assertRaisesNoChange(error, read, call)
        cmds.setAttr(name + ".tx", lock=True)
        cmds.setAttr(name + ".rz", lock=True)
        cmds.setAttr(name + ".sy", lock=True)
        for label, call in (
            ("translate", lambda: self.node.translateBy((1, 0, 0))),
            ("rotate", lambda: self.node.rotateBy((0, 0, 5))),
            ("scale", lambda: self.node.scaleBy(2)),
        ):
            with self.subTest(locked=label):
                self.assertRaisesNoChange(RuntimeError, read, call)
        free = self.transform("gone#")
        cmds.delete(free.getFullName())
        for call in (lambda: free.translateBy((1, 0, 0)), lambda: free.rotateBy((1, 0, 0)), lambda: free.scaleBy(2)):
            with self.assertRaises(RuntimeError):
                call()


class LimitsTest(_Case):
    """getLimits。"""

    def test_get_limits_round_trip(self):
        """setLimits で書いた値を同じ形で返し、別ノードへ写せる。無効な側は None。"""
        node = self.transform()
        node.setLimits(translateX=(-1, 2), rotateZ=(-45, None), scaleY=(None, 3))
        limits = node.getLimits()
        self.assertEqual(sorted(limits), sorted(prefix + axis for prefix in ("translate", "rotate", "scale") for axis in "XYZ"))
        self.assertEqual(limits["translateX"], (-1.0, 2.0))
        self.assertEqual(limits["rotateZ"][1], None)
        self.assertAlmostEqual(limits["rotateZ"][0], -45.0)
        self.assertEqual(limits["scaleY"], (None, 3.0))
        self.assertEqual(limits["translateY"], (None, None))
        self.assertAlmostEqual(node.getLimits(unit="rad")["rotateZ"][0], math.radians(-45))
        other = self.transform("other#")
        other.setLimits(**limits)
        self.assertEqual(other.getLimits(), limits)

    def test_matches_transform_limits_in_other_units(self):
        """UI の単位(mm・ラジアン)に依らず cm・度で返す。"""
        node = self.transform()
        cmds.transformLimits(node.getFullName(), translationY=(-2, 5), enableTranslationY=(True, True), rotationX=(-30, 60), enableRotationX=(True, True))
        cmds.currentUnit(linear="mm", angle="rad")
        limits = node.getLimits()
        self.assertSequenceAlmostEqual(limits["translateY"], (-2.0, 5.0))
        self.assertSequenceAlmostEqual(limits["rotateX"], (-30.0, 60.0))

    def test_invalid(self):
        node = self.transform()
        with self.assertRaises(ValueError):
            node.getLimits(unit="turn")
        cmds.delete(node.getFullName())
        with self.assertRaises(RuntimeError):
            node.getLimits()


class PivotAndUngroupTest(_Case):
    """zeroTransformPivots・ungroup。"""

    def pivoted(self, text):
        node = self.transform(text)
        name = node.getFullName()
        cmds.setAttr(name + ".t", 1, 2, 3)
        cmds.setAttr(name + ".r", 10, 20, 30)
        cmds.xform(name, rotatePivot=(1, 1, 1), scalePivot=(2, 0, 0), preserve=True)
        cmds.setAttr(name + ".s", 1, 2, 1)
        return node

    def test_zero_transform_pivots_matches_xform(self):
        """xform(zeroTransformPivots) と同じアトリビュートになり、ワールドのマトリクスを保つ。Undo 1回。"""
        node, reference = self.pivoted("node#"), self.pivoted("reference#")
        name = node.getFullName()
        matrix = cmds.xform(name, query=True, matrix=True, worldSpace=True)
        cmds.xform(reference.getFullName(), zeroTransformPivots=True)
        self.flushUndo()
        self.assertIs(node.zeroTransformPivots(), node)
        for attribute in ("t", "rp", "sp", "rpt", "spt"):
            with self.subTest(attribute):
                self.assertSequenceAlmostEqual(cmds.getAttr(name + "." + attribute)[0], cmds.getAttr(reference.getFullName() + "." + attribute)[0])
        self.assertSequenceAlmostEqual(cmds.xform(name, query=True, matrix=True, worldSpace=True), matrix)
        self.assertSequenceAlmostEqual(cmds.getAttr(name + ".rp")[0], (0, 0, 0))
        self.assertUndoesInOneStep(
            lambda: self.assertSequenceAlmostEqual(cmds.getAttr(name + ".rp")[0], (1, 1, 1)),
            lambda: self.assertSequenceAlmostEqual(cmds.getAttr(name + ".rp")[0], (0, 0, 0)),
        )

    def test_zero_transform_pivots_locked(self):
        """translate のロックは更新前に拒否し、何も変えない。削除済みは RuntimeError。"""
        node = self.pivoted("node#")
        name = node.getFullName()
        cmds.setAttr(name + ".tx", lock=True)
        self.assertRaisesNoChange(RuntimeError, lambda: cmds.getAttr(name + ".rp")[0], node.zeroTransformPivots)
        cmds.setAttr(name + ".tx", lock=False)
        cmds.delete(name)
        with self.assertRaises(RuntimeError):
            node.zeroTransformPivots()

    def test_ungroup(self):
        """子を親の下へ移して自身を消し、ワールドの位置を保つ。world=True はワールド直下。Undo 1回。"""
        top = self.transform("top#")
        group = self.transform("group#", top.getFullName())
        cmds.setAttr(group.getFullName() + ".t", 1, 0, 0)
        a = self.transform("a#", group.getFullName())
        b = self.transform("b#", group.getFullName())
        cmds.setAttr(a.getFullName() + ".t", 0, 2, 0)
        world_a = cmds.xform(a.getFullName(), query=True, translation=True, worldSpace=True)
        group_name = group.getFullName()
        self.flushUndo()
        children = group.ungroup()
        self.assertEqual([child.getUuid() for child in children], [a.getUuid(), b.getUuid()])
        self.assertFalse(cmds.objExists(group_name))
        self.assertEqual(children[0].getParent().getUuid(), top.getUuid())
        self.assertSequenceAlmostEqual(cmds.xform(children[0].getFullName(), query=True, translation=True, worldSpace=True), world_a)
        self.assertUndoesInOneStep(lambda: self.assertTrue(cmds.objExists(group_name)), lambda: self.assertFalse(cmds.objExists(group_name)))
        group = mlib.getNode(group_name)
        children = group.ungroup(world=True)
        self.assertTrue(all(child.getParent() is None for child in children))
        with self.assertRaises(TypeError):
            top.ungroup(world=1)
        with self.assertRaises(RuntimeError):
            group.ungroup()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
