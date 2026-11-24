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
    """setTranslation・setRotate・setScale・setShear の relative=True(今の値からの相対の変更)。"""

    def setUp(self):
        super().setUp()
        self.parent = self.transform("parent#")
        cmds.setAttr(self.parent.getName(full=True) + ".r", 10, 40, -20)
        # 親の非一様なスケールはワールドのマトリクスにシアーを生み、ワールド軸の回転が定まらないため一様にする。
        cmds.setAttr(self.parent.getName(full=True) + ".s", 2, 2, 2)
        self.node = self.transform("node#", self.parent.getName(full=True))
        self.reference = self.transform("reference#", self.parent.getName(full=True))
        for node in (self.node, self.reference):
            cmds.setAttr(node.getName(full=True) + ".t", 1, 2, 3)
            cmds.setAttr(node.getName(full=True) + ".r", 10, 20, 30)
            cmds.setAttr(node.getName(full=True) + ".ro", 2)
            cmds.setAttr(node.getName(full=True) + ".s", 1, 2, 3)

    def values(self, node, attribute):
        return cmds.getAttr(node.getName(full=True) + "." + attribute)[0]

    def test_translate_by_matches_cmds_move(self):
        """setTranslation(relative=True) は親の空間・ワールドの軸で cmds.move(relative) と同じ translate になる。"""
        ref = self.reference.getName(full=True)
        self.assertIsNone(self.node.setTranslation((1, -2, 0.5), relative=True))
        cmds.move(1, -2, 0.5, ref, relative=True, localSpace=True)
        self.assertSequenceAlmostEqual(self.values(self.node, "t"), self.values(self.reference, "t"))
        self.node.setTranslation((3, 0, 1), ws=True, relative=True)
        cmds.move(3, 0, 1, ref, relative=True, worldSpace=True)
        self.assertSequenceAlmostEqual(self.values(self.node, "t"), self.values(self.reference, "t"))

    def test_rotate_by_matches_cmds_rotate(self):
        """setRotate(relative=True) はローカル軸・ワールドの軸で cmds.rotate(relative) と同じ向きになる(rotateOrder=zxy)。"""
        ref = self.reference.getName(full=True)
        self.assertIsNone(self.node.setRotate((5, 15, 25), relative=True))
        cmds.rotate(5, 15, 25, ref, relative=True, objectSpace=True)
        self.assertSequenceAlmostEqual(self.values(self.node, "r"), self.values(self.reference, "r"), places=6)
        self.node.setRotate((math.radians(20), 0, math.radians(-10)), worldSpace=True, unit="rad", relative=True)
        cmds.rotate(20, 0, -10, ref, relative=True, worldSpace=True)
        self.assertSequenceAlmostEqual(
            cmds.xform(self.node.getName(full=True), query=True, matrix=True, worldSpace=True),
            cmds.xform(ref, query=True, matrix=True, worldSpace=True),
            places=6,
        )

    def test_rotate_by_accumulates(self):
        """90度ずつ4回回すと rotate は360度へ進む(等価解を今の値の近くに選ぶ)。"""
        node = self.transform("free#")
        for _ in range(4):
            node.setRotate((0, 0, 90), relative=True)
        self.assertAlmostEqual(cmds.getAttr(node.getName(full=True) + ".rz"), 360.0, places=6)
        quarter = om2.MEulerRotation(0.0, math.radians(90), 0.0)
        node.setRotate(quarter, relative=True)
        self.assertAlmostEqual(cmds.getAttr(node.getName(full=True) + ".ry"), 90.0, places=6)
        # クォータニオンも回転量として受ける。
        node.setRotate(mlib.Quaternion(quarter.asQuaternion()), relative=True)
        self.assertAlmostEqual(cmds.getAttr(node.getName(full=True) + ".ry"), 180.0, places=6)

    def test_scale_by(self):
        """setScale(relative=True) は scale へ倍率を掛ける。数値1つは XYZ 共通。"""
        self.assertIsNone(self.node.setScale((2, 0.5, 1), relative=True))
        self.assertSequenceAlmostEqual(self.values(self.node, "s"), (2, 1, 3))
        self.node.setScale(3, relative=True)
        self.assertSequenceAlmostEqual(self.values(self.node, "s"), (6, 3, 9))

    def test_shear_by(self):
        """setShear(relative=True) は shear の XY・XZ・YZ へ成分ごとに倍率を掛ける(0 の成分は 0 のまま)。"""
        name = self.node.getName(full=True)
        cmds.setAttr(name + ".shear", 0.5, 0.0, 0.2)
        self.assertIsNone(self.node.setShear((2, 3, 0.5), relative=True))
        self.assertSequenceAlmostEqual(self.values(self.node, "shear"), (1.0, 0.0, 0.1))
        # MFnTransform.shearBy と同じ結果になる。
        cmds.setAttr(self.reference.getName(full=True) + ".shear", 0.5, 0.0, 0.2)
        om2.MFnTransform(self.reference.mpath()).shearBy((2, 3, 0.5))
        self.assertSequenceAlmostEqual(self.values(self.node, "shear"), self.values(self.reference, "shear"))

    def relative_calls(self):
        """(ラベル, アトリビュート, 相対の変更を呼ぶ関数)を返す。関数は node とキーワード引数を受ける。"""
        return (
            ("translate", "t", lambda node, **flags: node.setTranslation((1, 2, 3), relative=True, **flags)),
            ("translate ws", "t", lambda node, **flags: node.setTranslation((1, 2, 3), ws=True, relative=True, **flags)),
            ("rotate", "r", lambda node, **flags: node.setRotate((10, 0, 5), relative=True, **flags)),
            ("rotate ws", "r", lambda node, **flags: node.setRotate((10, 0, 5), ws=True, relative=True, **flags)),
            ("scale", "s", lambda node, **flags: node.setScale((2, 3, 0.5), relative=True, **flags)),
            ("scale uniform", "s", lambda node, **flags: node.setScale(2, relative=True, **flags)),
            ("shear", "shear", lambda node, **flags: node.setShear((2, 3, 0.5), relative=True, **flags)),
        )

    def test_undo_one_step(self):
        """各メソッドの relative=True は Undo 1 回で戻る。"""
        name = self.node.getName(full=True)
        cmds.setAttr(name + ".shear", 0.5, 0.25, 0.1)
        before = cmds.xform(name, query=True, matrix=True)
        for label, _attribute, call in self.relative_calls():
            with self.subTest(label):
                self.flushUndo()
                self.assertIsNone(call(self.node))
                self.assertUndoesInOneStep(
                    lambda: self.assertSequenceAlmostEqual(cmds.xform(name, query=True, matrix=True), before),
                    lambda: self.assertNotEqual(cmds.xform(name, query=True, matrix=True), before),
                )

    def test_relative_fast_matches_normal_without_undo(self):
        """relative=True の fast=True は通常と同じ値を書き、Undo に記録しない。"""
        for node in (self.node, self.reference):
            cmds.setAttr(node.getName(full=True) + ".shear", 0.5, 0.25, 0.1)
        for label, attribute, call in self.relative_calls():
            with self.subTest(label):
                call(self.reference)
                self.flushUndo()
                self.assertIsNone(call(self.node, fast=True))
                self.assertUndoEmpty()
                self.assertSequenceAlmostEqual(self.values(self.node, attribute), self.values(self.reference, attribute), places=6)

    def test_relative_get_returns_planned_value_without_writing(self):
        """relative=True の get=True は書き込まずに、書き込む予定のローカルの値を返す。"""
        expected_types = {"t": mlib.Translate, "r": mlib.EulerRotate, "s": mlib.Scale, "shear": mlib.Shear}
        for node in (self.node, self.reference):
            cmds.setAttr(node.getName(full=True) + ".shear", 0.5, 0.25, 0.1)
        for label, attribute, call in self.relative_calls():
            for fast in (False, True):
                with self.subTest(label, fast=fast):
                    before = self.values(self.node, attribute)
                    self.flushUndo()
                    planned = call(self.node, get=True, fast=fast)
                    self.assertIsInstance(planned, expected_types[attribute])
                    self.assertEqual(self.values(self.node, attribute), before)
                    self.assertUndoEmpty()
                    # 同じ状態の reference へ実際に書いた値と一致する。
                    state = self.values(self.reference, attribute)
                    call(self.reference)
                    written = self.values(self.reference, attribute)
                    cmds.setAttr(self.reference.getName(full=True) + "." + attribute, *state)
                    planned = [math.degrees(value) for value in planned] if attribute == "r" else list(planned)
                    self.assertSequenceAlmostEqual(planned, written, places=6)

    def test_relative_safe_skips_locked_components(self):
        """relative=True の safe=True は、ロックした成分を無視して残りを書く(通常・fast とも)。"""
        cases = (
            ("translate", "t", "tx", lambda node, **flags: node.setTranslation((1, 2, 3), relative=True, **flags), (None, 4.0, 6.0)),
            ("scale", "s", "sy", lambda node, **flags: node.setScale((2, 3, 0.5), relative=True, **flags), (2.0, None, 1.5)),
            ("shear", "shear", "shearXZ", lambda node, **flags: node.setShear((2, 3, 0.5), relative=True, **flags), (1.0, None, 0.05)),
        )
        for label, attribute, locked, call, expected in cases:
            for fast in (False, True):
                with self.subTest(label, fast=fast):
                    node = self.transform("safe#", self.parent.getName(full=True))
                    name = node.getName(full=True)
                    cmds.setAttr(name + ".t", 1, 2, 3)
                    cmds.setAttr(name + ".s", 1, 2, 3)
                    cmds.setAttr(name + ".shear", 0.5, 0.25, 0.1)
                    before = self.values(node, attribute)
                    cmds.setAttr(name + "." + locked, lock=True)
                    with self.assertRaises(RuntimeError):
                        call(node, fast=fast, check=True)
                    self.assertEqual(self.values(node, attribute), before)
                    self.assertIsNone(call(node, safe=True, fast=fast))
                    after = self.values(node, attribute)
                    for index, value in enumerate(expected):
                        self.assertAlmostEqual(after[index], before[index] if value is None else value)
        # 回転は、ロックした成分を除いた残りの成分だけを書く。
        for fast in (False, True):
            with self.subTest("rotate", fast=fast):
                node = self.transform("safeRotate#")
                name = node.getName(full=True)
                cmds.setAttr(name + ".rz", lock=True)
                self.assertIsNone(node.setRotate((10, 20, 30), relative=True, safe=True, fast=fast))
                rotate = cmds.getAttr(name + ".r")[0]
                self.assertAlmostEqual(rotate[2], 0.0)
                self.assertNotAlmostEqual(rotate[0], 0.0)

    def test_relative_check_matches_default_when_writable(self):
        """relative=True の check=True は、書き込めるなら既定と同じ結果になる(通常・fast とも)。"""
        for node in (self.node, self.reference):
            cmds.setAttr(node.getName(full=True) + ".shear", 0.5, 0.25, 0.1)
        for label, attribute, call in self.relative_calls():
            for fast in (False, True):
                with self.subTest(label, fast=fast):
                    call(self.reference)
                    self.assertIsNone(call(self.node, check=True, fast=fast))
                    self.assertSequenceAlmostEqual(self.values(self.node, attribute), self.values(self.reference, attribute), places=6)

    def test_relative_exclusive_arguments(self):
        """relative=True は、setTranslation の at、setScale・setShear の worldSpace と同時に指定できない(TypeError)。"""
        name = self.node.getName(full=True)

        def read():
            return cmds.xform(name, query=True, matrix=True)

        for label, call in (
            ("translate at=0", lambda: self.node.setTranslation((1, 0, 0), at=0, relative=True)),
            ("translate at=1", lambda: self.node.setTranslation((1, 0, 0), at=1, relative=True)),
            ("scale worldSpace", lambda: self.node.setScale((2, 2, 2), worldSpace=True, relative=True)),
            ("scale ws", lambda: self.node.setScale(2, ws=True, relative=True)),
            ("shear worldSpace", lambda: self.node.setShear((2, 2, 2), worldSpace=True, relative=True)),
            ("translate relative int", lambda: self.node.setTranslation((1, 0, 0), relative=1)),
            ("rotate relative int", lambda: self.node.setRotate((1, 0, 0), relative=1)),
            ("scale relative int", lambda: self.node.setScale((1, 1, 1), relative=1)),
            ("shear relative int", lambda: self.node.setShear((1, 1, 1), relative=None)),
        ):
            with self.subTest(label):
                self.assertRaisesNoChange(TypeError, read, call)
        # relative=False(既定)は今までどおり絶対の値として書く。
        self.node.setScale((2, 2, 2), relative=False)
        self.assertSequenceAlmostEqual(self.values(self.node, "s"), (2, 2, 2))

    def test_invalid_input(self):
        """不正な入力・ロック・削除済みノードは例外で、値を変えない。"""
        name = self.node.getName(full=True)

        def read():
            return cmds.xform(name, query=True, matrix=True)

        for label, error, call in (
            ("translate 2", ValueError, lambda: self.node.setTranslation((1, 2), relative=True)),
            ("translate str", TypeError, lambda: self.node.setTranslation("abc", relative=True)),
            ("translate nan", ValueError, lambda: self.node.setTranslation((1, float("nan"), 0), relative=True)),
            ("translate ws twice", TypeError, lambda: self.node.setTranslation((1, 0, 0), True, ws=True, relative=True)),
            ("translate ws int", TypeError, lambda: self.node.setTranslation((1, 0, 0), worldSpace=1, relative=True)),
            ("rotate unit", ValueError, lambda: self.node.setRotate((1, 0, 0), unit="turn", relative=True)),
            ("rotate 4", ValueError, lambda: self.node.setRotate((1, 0, 0, 0), relative=True)),
            ("rotate nan", ValueError, lambda: self.node.setRotate((1, float("nan"), 0), relative=True)),
            ("shear 2", ValueError, lambda: self.node.setShear((1, 2), relative=True)),
            ("shear str", TypeError, lambda: self.node.setShear("abc", relative=True)),
            ("scale bool", TypeError, lambda: self.node.setScale(True, relative=True)),
            ("scale inf", ValueError, lambda: self.node.setScale(float("inf"), relative=True)),
        ):
            with self.subTest(label):
                self.assertRaisesNoChange(error, read, call)
        cmds.setAttr(name + ".tx", lock=True)
        cmds.setAttr(name + ".rz", lock=True)
        cmds.setAttr(name + ".sy", lock=True)
        for label, call in (
            ("translate", lambda: self.node.setTranslation((1, 0, 0), relative=True)),
            ("rotate", lambda: self.node.setRotate((0, 0, 5), relative=True)),
            ("scale", lambda: self.node.setScale(2, relative=True)),
        ):
            with self.subTest(locked=label):
                self.assertRaisesNoChange(RuntimeError, read, call)
        free = self.transform("gone#")
        cmds.delete(free.getName(full=True))
        for call in (
            lambda: free.setTranslation((1, 0, 0), relative=True),
            lambda: free.setRotate((1, 0, 0), relative=True),
            lambda: free.setScale(2, relative=True),
            lambda: free.setShear((2, 2, 2), relative=True),
        ):
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
        cmds.transformLimits(node.getName(full=True), translationY=(-2, 5), enableTranslationY=(True, True), rotationX=(-30, 60), enableRotationX=(True, True))
        cmds.currentUnit(linear="mm", angle="rad")
        limits = node.getLimits()
        self.assertSequenceAlmostEqual(limits["translateY"], (-2.0, 5.0))
        self.assertSequenceAlmostEqual(limits["rotateX"], (-30.0, 60.0))

    def test_invalid(self):
        node = self.transform()
        with self.assertRaises(ValueError):
            node.getLimits(unit="turn")
        cmds.delete(node.getName(full=True))
        with self.assertRaises(RuntimeError):
            node.getLimits()


class PivotAndUngroupTest(_Case):
    """zeroTransformPivots・ungroup。"""

    def pivoted(self, text):
        node = self.transform(text)
        name = node.getName(full=True)
        cmds.setAttr(name + ".t", 1, 2, 3)
        cmds.setAttr(name + ".r", 10, 20, 30)
        cmds.xform(name, rotatePivot=(1, 1, 1), scalePivot=(2, 0, 0), preserve=True)
        cmds.setAttr(name + ".s", 1, 2, 1)
        return node

    def test_zero_transform_pivots_matches_xform(self):
        """xform(zeroTransformPivots) と同じアトリビュートになり、ワールドのマトリクスを保つ。Undo 1回。"""
        node, reference = self.pivoted("node#"), self.pivoted("reference#")
        name = node.getName(full=True)
        matrix = cmds.xform(name, query=True, matrix=True, worldSpace=True)
        cmds.xform(reference.getName(full=True), zeroTransformPivots=True)
        self.flushUndo()
        self.assertIsNone(node.zeroTransformPivots())
        for attribute in ("t", "rp", "sp", "rpt", "spt"):
            with self.subTest(attribute):
                self.assertSequenceAlmostEqual(cmds.getAttr(name + "." + attribute)[0], cmds.getAttr(reference.getName(full=True) + "." + attribute)[0])
        self.assertSequenceAlmostEqual(cmds.xform(name, query=True, matrix=True, worldSpace=True), matrix)
        self.assertSequenceAlmostEqual(cmds.getAttr(name + ".rp")[0], (0, 0, 0))
        self.assertUndoesInOneStep(
            lambda: self.assertSequenceAlmostEqual(cmds.getAttr(name + ".rp")[0], (1, 1, 1)),
            lambda: self.assertSequenceAlmostEqual(cmds.getAttr(name + ".rp")[0], (0, 0, 0)),
        )

    def test_zero_transform_pivots_locked(self):
        """translate のロックは更新前に拒否し、何も変えない。削除済みは RuntimeError。"""
        node = self.pivoted("node#")
        name = node.getName(full=True)
        cmds.setAttr(name + ".tx", lock=True)
        self.assertRaisesNoChange(RuntimeError, lambda: cmds.getAttr(name + ".rp")[0], node.zeroTransformPivots)
        cmds.setAttr(name + ".tx", lock=False)
        cmds.delete(name)
        with self.assertRaises(RuntimeError):
            node.zeroTransformPivots()

    def test_ungroup(self):
        """子を親の下へ移して自身を消し、ワールドの位置を保つ。world=True はワールド直下。Undo 1回。"""
        top = self.transform("top#")
        group = self.transform("group#", top.getName(full=True))
        cmds.setAttr(group.getName(full=True) + ".t", 1, 0, 0)
        a = self.transform("a#", group.getName(full=True))
        b = self.transform("b#", group.getName(full=True))
        cmds.setAttr(a.getName(full=True) + ".t", 0, 2, 0)
        world_a = cmds.xform(a.getName(full=True), query=True, translation=True, worldSpace=True)
        group_name = group.getName(full=True)
        self.flushUndo()
        children = group.ungroup()
        self.assertEqual([child.getUuid() for child in children], [a.getUuid(), b.getUuid()])
        self.assertFalse(cmds.objExists(group_name))
        self.assertEqual(children[0].getParent().getUuid(), top.getUuid())
        self.assertSequenceAlmostEqual(cmds.xform(children[0].getName(full=True), query=True, translation=True, worldSpace=True), world_a)
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
