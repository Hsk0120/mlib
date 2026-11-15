"""``Transform.setTranslation(worldSpace=True)`` のテスト。

回転ピボットがワールドの目標の位置へ来ること(ピボットの有無・親の変換・offsetParentMatrix・Joint・UIの単位)、
ピボットが無いときの値が ``cmds.xform`` と一致すること、ロックされた成分の拒否、Undo 1回を確かめる。
"""

import itertools
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.nodes import Node

TARGET = (4.5, -2.25, 7.75)


class WorldTranslationTest(NamespaceCase):
    PREFIX = "mlibTransformWorldTranslation_"

    def tearDown(self):
        cmds.currentUnit(linear="cm")
        super().tearDown()

    def build(self, kind="transform", parent_scale=(1, 1, 1), pivots=False, opm=False):
        cmds.select(clear=True)
        parent = self.make(kind, "parent#")
        cmds.setAttr(parent + ".t", 1, 2, 3)
        cmds.setAttr(parent + ".r", 20, 30, 40)
        cmds.setAttr(parent + ".s", *parent_scale)
        cmds.select(clear=True)
        node = self.make(kind, "node#", parent=parent)
        if kind == "joint":
            cmds.connectAttr(parent + ".scale", node + ".inverseScale")
            cmds.setAttr(node + ".jointOrient", 10, 20, 30)
        cmds.setAttr(node + ".t", 0.5, 1.5, -2.5)
        cmds.setAttr(node + ".r", 15, -25, 35)
        cmds.setAttr(node + ".s", 1.5, 0.5, 2)
        cmds.setAttr(node + ".rotateAxis", 5, 10, 15)
        if pivots:
            cmds.setAttr(node + ".rotatePivot", 0.5, 0.2, 0.1)
            cmds.setAttr(node + ".rotatePivotTranslate", 0.2, 0.0, 0.1)
            cmds.setAttr(node + ".scalePivot", 0.1, 0.3, -0.2)
        if opm:
            cmds.setAttr(node + ".offsetParentMatrix", [1, 0, 0, 0, 0, 0.8, 0.6, 0, 0, -0.6, 0.8, 0, 2, 1, -1, 1], type="matrix")
        return node

    def test_rotate_pivot_reaches_target(self):
        cases = itertools.product(("transform", "joint"), ((1, 1, 1), (2, 3, 0.5), (-1, 1, 1)), (False, True), (False, True), ("cm", "m"))
        for kind, parent_scale, pivots, opm, unit in cases:
            with self.subTest(kind=kind, parentScale=parent_scale, pivots=pivots, opm=opm, unit=unit):
                cmds.currentUnit(linear=unit)
                name = self.build(kind, parent_scale, pivots, opm)
                node = Node(name)
                self.assertIsNone(node.setTranslation(TARGET, worldSpace=True))
                if not (kind == "joint" and pivots):
                    # Jointはピボットをマトリクスに使わないので、xformの問い合わせとは比べない。
                    # xformの問い合わせはUIの単位で返るので、cmへ直して比べる。
                    factor = 100.0 if unit == "m" else 1.0
                    world = [value * factor for value in cmds.xform(name, query=True, worldSpace=True, rotatePivot=True)]
                    self.assertSequenceAlmostEqual(world, TARGET, places=6)
                self.assertSequenceAlmostEqual(tuple(node.getTranslation(worldSpace=True)), TARGET, places=6)

    def test_matches_xform_without_pivots(self):
        for kind, parent_scale, opm in itertools.product(("transform", "joint"), ((2, 3, 0.5), (-1, 1, 1)), (False, True)):
            with self.subTest(kind=kind, parentScale=parent_scale, opm=opm):
                by_xform = self.build(kind, parent_scale, False, opm)
                cmds.xform(by_xform, worldSpace=True, translation=TARGET)
                by_mlib = self.build(kind, parent_scale, False, opm)
                Node(by_mlib).setTranslation(TARGET, worldSpace=True)
                self.assertSequenceAlmostEqual(cmds.getAttr(by_mlib + ".t")[0], cmds.getAttr(by_xform + ".t")[0], places=9)

    def test_each_base_point_and_get(self):
        """基準点(at)ごとに、設定した後の同じ基準点の位置が目標になる。get=Trueは値を返すだけで書かない。"""
        for pivots, at in itertools.product((False, True), (0, 1, 2, 3, 4)):
            with self.subTest(pivots=pivots, at=at):
                name = self.build(pivots=pivots)
                node = Node(name)
                before = cmds.getAttr(name + ".t")
                planned = node.setTranslation(TARGET, worldSpace=True, at=at, get=True)
                self.assertEqual(cmds.getAttr(name + ".t"), before)
                node.setTranslation(TARGET, worldSpace=True, at=at)
                self.assertSequenceAlmostEqual(cmds.getAttr(name + ".t")[0], planned, places=9)
                if at >= 1:
                    self.assertSequenceAlmostEqual(tuple(node.getTranslation(worldSpace=True, at=at)), TARGET, places=6)

    def test_locked_or_connected_channel_is_rejected(self):
        source = self.make("transform", "source#")
        for case, pivots in itertools.product(("lock", "connect"), (False, True)):
            with self.subTest(case=case, pivots=pivots):
                name = self.build(pivots=pivots)
                if case == "lock":
                    cmds.setAttr(name + ".ty", lock=True)
                else:
                    cmds.connectAttr(source + ".tx", name + ".ty")
                before = cmds.getAttr(name + ".t")
                self.flushUndo()
                with self.assertRaises(RuntimeError):
                    Node(name).setTranslation(TARGET, worldSpace=True)
                self.assertEqual(cmds.getAttr(name + ".t"), before)
                self.assertUndoEmpty()

    def test_undo_is_one_step_and_fast_is_not_recorded(self):
        for pivots in (False, True):
            with self.subTest(pivots=pivots):
                name = self.build(pivots=pivots)
                node = Node(name)
                before = cmds.getAttr(name + ".t")
                self.flushUndo()
                node.setTranslation(TARGET, worldSpace=True)
                after = cmds.getAttr(name + ".t")
                self.assertUndoesInOneStep(
                    lambda: self.assertEqual(cmds.getAttr(name + ".t"), before), lambda: self.assertEqual(cmds.getAttr(name + ".t"), after)
                )
                node.setTranslation(TARGET, worldSpace=True, fast=True)
                self.assertSequenceAlmostEqual(cmds.getAttr(name + ".t")[0], after[0], places=9)
                self.assertUndoEmpty()


if __name__ == "__main__":
    unittest.main()
