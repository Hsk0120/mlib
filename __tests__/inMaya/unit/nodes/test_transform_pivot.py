"""``mlib.nodes.transform`` のテスト。

- Transform の参照の少ない公開APIの約束を固定する(担当C)。
"""

import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.nodes import Node

TOLERANCE = 1e-9


class _SpecCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、共通基底からの差分。"""

    PREFIX = "mlibSpecXformMisc_"


class ResetPivotTest(_SpecCase):
    """setPivot((0, 0, 0), ws=True, kind="both") は姿勢を保ってピボットを原点へ移す。"""

    def setUp(self):
        super().setUp()
        self.parent = self.make("transform", "parent")
        cmds.setAttr(self.parent + ".translate", 1, 0, 0)
        self.name_ = self.make("transform", "pivot", parent=self.parent)
        cmds.setAttr(self.name_ + ".rotate", 0, 30, 0)
        cmds.xform(self.name_, worldSpace=True, rotatePivot=(1, 2, 3), scalePivot=(4, 5, 6))
        self.node = Node(self.name_)
        self.matrix = cmds.getAttr(self.name_ + ".worldMatrix[0]")

    def world_pivots(self):
        return (cmds.xform(self.name_, query=True, worldSpace=True, rotatePivot=True), cmds.xform(self.name_, query=True, worldSpace=True, scalePivot=True))

    def test_both_world_and_undo(self):
        """既定は両方のピボットをワールド原点へ移し、姿勢を変えない。1回の Undo で戻る。"""
        cmds.flushUndo()
        self.assertIs(self.node.setPivot((0, 0, 0), worldSpace=True, kind="both"), self.node)
        rotate_pivot, scale_pivot = self.world_pivots()
        self.assertSequenceAlmostEqual(rotate_pivot, [0, 0, 0])
        self.assertSequenceAlmostEqual(scale_pivot, [0, 0, 0])
        self.assertSequenceAlmostEqual(cmds.getAttr(self.name_ + ".worldMatrix[0]"), self.matrix)
        self.assertSequenceAlmostEqual(cmds.getAttr(self.name_ + ".translate")[0], [0, 0, 0])
        cmds.undo()
        rotate_pivot, _ = self.world_pivots()
        self.assertSequenceAlmostEqual(rotate_pivot, [1, 2, 3])

    def test_kind_and_object_space(self):
        """kind=rotate は回転ピボットだけ、ws=False は object 空間の原点へ移す。"""
        self.node.setPivot((0, 0, 0), worldSpace=True, kind="rotate")
        rotate_pivot, scale_pivot = self.world_pivots()
        self.assertSequenceAlmostEqual(rotate_pivot, [0, 0, 0])
        self.assertSequenceAlmostEqual(scale_pivot, [4, 5, 6])
        self.node.setPivot((0, 0, 0), worldSpace=False, kind="scale")
        self.assertSequenceAlmostEqual(cmds.xform(self.name_, query=True, objectSpace=True, scalePivot=True), [0, 0, 0])
        self.assertSequenceAlmostEqual(cmds.getAttr(self.name_ + ".worldMatrix[0]"), self.matrix)

    def test_fast_matches_and_is_not_recorded(self):
        """fast=True も同じ結果で、Undo に記録しない。"""
        cmds.flushUndo()
        self.node.setPivot((0, 0, 0), worldSpace=True, fast=True, kind="both")
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
        rotate_pivot, scale_pivot = self.world_pivots()
        self.assertSequenceAlmostEqual(rotate_pivot, [0, 0, 0])
        self.assertSequenceAlmostEqual(scale_pivot, [0, 0, 0])
        self.assertSequenceAlmostEqual(cmds.getAttr(self.name_ + ".worldMatrix[0]"), self.matrix)

    def test_errors(self):
        """kind・ws の不正は ValueError、Joint・fast の型は TypeError。"""
        with self.assertRaisesRegex(ValueError, "kind"):
            self.node.setPivot((0, 0, 0), worldSpace=True, kind="both2")
        with self.assertRaises(TypeError):
            self.node.setPivot((0, 0, 0), worldSpace=1, kind="both")
        with self.assertRaisesRegex(TypeError, "fast must be a bool"):
            self.node.setPivot((0, 0, 0), worldSpace=True, fast=1, kind="both")
        with self.assertRaisesRegex(TypeError, "Joint does not support"):
            Node(self.make("joint", "jointPivot")).setPivot((0, 0, 0), worldSpace=True, kind="both")

    def test_locked_pivot(self):
        """ロックされたピボットの成分は通常・fast とも RuntimeError で、何も変えない。"""
        cmds.setAttr(self.name_ + ".rotatePivotX", lock=True)
        before = [cmds.getAttr(self.name_ + "." + name)[0] for name in ("rotatePivot", "rotatePivotTranslate", "scalePivot", "scalePivotTranslate")]
        cmds.flushUndo()
        for fast in (True, False):
            for kind in ("rotate", "both"):
                with self.assertRaisesRegex(RuntimeError, "locked or connected"):
                    self.node.setPivot((0, 0, 0), worldSpace=True, kind=kind, fast=fast)
                with self.assertRaisesRegex(RuntimeError, "locked or connected"):
                    self.node.setPivot((0, 0, 0), kind=kind, fast=fast)
            with self.assertRaisesRegex(RuntimeError, "locked or connected"):
                self.node.centerPivot(fast=fast)
        after = [cmds.getAttr(self.name_ + "." + name)[0] for name in ("rotatePivot", "rotatePivotTranslate", "scalePivot", "scalePivotTranslate")]
        self.assertEqual(after, before)
        self.assertSequenceAlmostEqual(cmds.getAttr(self.name_ + ".worldMatrix[0]"), self.matrix)
        # ロックされていない種類は変更できる。
        self.node.setPivot((0, 0, 0), worldSpace=True, kind="scale")
        _, scale_pivot = self.world_pivots()
        self.assertSequenceAlmostEqual(scale_pivot, [0, 0, 0])

    def test_locked_pivot_translate(self):
        """preserve=True で書き換える補償値のロックも通常・fast とも拒否し、preserve=False は通る。"""
        cmds.setAttr(self.name_ + ".rotatePivotTranslateY", lock=True)
        for fast in (True, False):
            with self.assertRaisesRegex(RuntimeError, "locked or connected"):
                self.node.setPivot((0, 0, 0), worldSpace=True, fast=fast)
        translate_before = cmds.getAttr(self.name_ + ".rotatePivotTranslate")[0]
        self.assertSequenceAlmostEqual(cmds.getAttr(self.name_ + ".worldMatrix[0]"), self.matrix)
        # 補償値を書かない preserve=False はロックに当たらない。
        self.node.setPivot((0, 0, 0), worldSpace=False, preserve=False)
        self.assertSequenceAlmostEqual(cmds.getAttr(self.name_ + ".rotatePivot")[0], [0, 0, 0])
        self.assertEqual(cmds.getAttr(self.name_ + ".rotatePivotTranslate")[0], translate_before)


if __name__ == "__main__":
    unittest.main()
