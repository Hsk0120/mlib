"""``mlib.nodes.transform`` のテスト。

- Transform の参照の少ない公開APIの約束を固定する(担当C)。
"""

import unittest

import maya.api.OpenMaya as om2
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
        self.assertIsNone(self.node.setPivot((0, 0, 0), worldSpace=True, kind="both"))
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
        with self.assertRaisesRegex(TypeError, "fastはboolで指定してください"):
            self.node.setPivot((0, 0, 0), worldSpace=True, fast=1, kind="both")
        with self.assertRaisesRegex(TypeError, "Jointは回転とスケールのピボットを別々に持てません"):
            Node(self.make("joint", "jointPivot")).setPivot((0, 0, 0), worldSpace=True, kind="both")

    def test_locked_pivot(self):
        """ロックされたピボットの成分は、通常と fast(check=True)で RuntimeError になり、何も変えない。"""
        cmds.setAttr(self.name_ + ".rotatePivotX", lock=True)
        before = [cmds.getAttr(self.name_ + "." + name)[0] for name in ("rotatePivot", "rotatePivotTranslate", "scalePivot", "scalePivotTranslate")]
        cmds.flushUndo()
        for fast in (True, False):
            for kind in ("rotate", "both"):
                with self.assertRaisesRegex(RuntimeError, "ロックされているか、接続されています"):
                    self.node.setPivot((0, 0, 0), worldSpace=True, kind=kind, fast=fast, check=True)
                with self.assertRaisesRegex(RuntimeError, "ロックされているか、接続されています"):
                    self.node.setPivot((0, 0, 0), kind=kind, fast=fast, check=True)
            with self.assertRaisesRegex(RuntimeError, "ロックされているか、接続されています"):
                self.node.centerPivot(fast=fast, check=True)
        after = [cmds.getAttr(self.name_ + "." + name)[0] for name in ("rotatePivot", "rotatePivotTranslate", "scalePivot", "scalePivotTranslate")]
        self.assertEqual(after, before)
        self.assertSequenceAlmostEqual(cmds.getAttr(self.name_ + ".worldMatrix[0]"), self.matrix)
        # ロックされていない種類は変更できる。
        self.node.setPivot((0, 0, 0), worldSpace=True, kind="scale")
        _, scale_pivot = self.world_pivots()
        self.assertSequenceAlmostEqual(scale_pivot, [0, 0, 0])

    def test_locked_pivot_translate(self):
        """preserve=True で書き換える補償値のロックも通常・fast(check=True)で拒否し、preserve=False は通る。"""
        cmds.setAttr(self.name_ + ".rotatePivotTranslateY", lock=True)
        for fast in (True, False):
            with self.assertRaisesRegex(RuntimeError, "ロックされているか、接続されています"):
                self.node.setPivot((0, 0, 0), worldSpace=True, fast=fast, check=True)
        translate_before = cmds.getAttr(self.name_ + ".rotatePivotTranslate")[0]
        self.assertSequenceAlmostEqual(cmds.getAttr(self.name_ + ".worldMatrix[0]"), self.matrix)
        # 補償値を書かない preserve=False はロックに当たらない。
        self.node.setPivot((0, 0, 0), worldSpace=False, preserve=False)
        self.assertSequenceAlmostEqual(cmds.getAttr(self.name_ + ".rotatePivot")[0], [0, 0, 0])
        self.assertEqual(cmds.getAttr(self.name_ + ".rotatePivotTranslate")[0], translate_before)


class CenterPivotOnComponentsTest(_SpecCase):
    """centerPivot(components) は、渡した頂点・CVのワールドのバウンディングボックスの中心へ両方のピボットを動かす。"""

    def setUp(self):
        super().setUp()
        self.parent = self.make("transform", "centerParent")
        cmds.setAttr(self.parent + ".translate", 1, 2, 3)
        cmds.setAttr(self.parent + ".rotate", 0, 30, 0)

    def cube(self):
        """親の下に、動かして回した cube を作ってラッパーを返す。"""
        name = cmds.polyCube(name=self.name("centerCube#"), constructionHistory=False)[0]
        name = cmds.ls(cmds.parent(name, self.parent)[0], long=True)[0]
        cmds.setAttr(name + ".translate", 0.5, -1, 2)
        cmds.setAttr(name + ".rotate", 10, 20, 30)
        cmds.setAttr(name + ".scale", 1, 2, 1)
        cmds.select(clear=True)
        return Node(name)

    @staticmethod
    def expected_center(name, components):
        """コンポーネントのワールドのバウンディングボックスの中心を cmds で求める。"""
        points = cmds.xform(name + components, query=True, translation=True, worldSpace=True)
        rows = [points[index : index + 3] for index in range(0, len(points), 3)]
        return [(min(row[axis] for row in rows) + max(row[axis] for row in rows)) * 0.5 for axis in range(3)]

    @staticmethod
    def pivots(name):
        return (cmds.xform(name, query=True, worldSpace=True, rotatePivot=True), cmds.xform(name, query=True, worldSpace=True, scalePivot=True))

    def test_fast_matches_normal_and_records_no_undo(self):
        """fast=True は通常と同じピボットになり、姿勢を変えず、Undo に記録しない。通常は 1 回の Undo で戻る。"""
        for components in (".vtx[0:1]", ".vtx[0]", ".vtx[*]"):
            for fast in (False, True):
                with self.subTest(components=components, fast=fast):
                    node = self.cube()
                    name = node.getFullName()
                    matrix = cmds.getAttr(name + ".worldMatrix[0]")
                    before = self.pivots(name)
                    expected = self.expected_center(name, components)
                    cmds.flushUndo()
                    self.assertIsNone(node.centerPivot(name + components, fast=fast))
                    for pivot in self.pivots(name):
                        self.assertSequenceAlmostEqual(pivot, expected, places=6)
                    self.assertSequenceAlmostEqual(cmds.getAttr(name + ".worldMatrix[0]"), matrix, places=6)
                    if fast:
                        self.assertUndoEmpty()
                    else:
                        cmds.undo()
                        self.assertUndoEmpty()
                        for pivot, old in zip(self.pivots(name), before):
                            self.assertSequenceAlmostEqual(pivot, old, places=6)

    def test_accepts_component_objects_and_keeps_selection(self):
        """Vertices などのコンポーネントも受け、今の選択は使わず変えない(fast でも同じ)。"""
        for fast in (False, True):
            with self.subTest(fast=fast):
                node = self.cube()
                name = node.getFullName()
                cmds.select(name + ".vtx[6:7]", replace=True)
                selection = cmds.ls(selection=True)
                node.centerPivot(node.getShape().getVertices([2, 3]), fast=fast)
                self.assertEqual(cmds.ls(selection=True), selection)
                for pivot in self.pivots(name):
                    self.assertSequenceAlmostEqual(pivot, self.expected_center(name, ".vtx[2:3]"), places=6)
                cmds.select(clear=True)

    def test_curve_cvs(self):
        """NURBS カーブの CV でも同じ(通常・fast)。"""
        for fast in (False, True):
            with self.subTest(fast=fast):
                name = cmds.ls(cmds.curve(name=self.name("centerCurve#"), degree=1, point=[(0, 0, 0), (2, 0, 0), (2, 4, 0), (0, 4, 6)]), long=True)[0]
                cmds.setAttr(name + ".translate", 1, 1, 1)
                cmds.select(clear=True)
                Node(name).centerPivot(name + ".cv[1:3]", fast=fast)
                for pivot in self.pivots(name):
                    self.assertSequenceAlmostEqual(pivot, self.expected_center(name, ".cv[1:3]"), places=6)

    def test_check_rejects_locked_pivot_without_writing(self):
        """ピボットの成分がロックされていると、通常と check=True では書く前に RuntimeError(fast だけの指定は確かめない)。"""
        for fast in (False, True):
            for check in (False, True):
                if fast and not check:
                    continue
                with self.subTest(fast=fast, check=check):
                    node = self.cube()
                    name = node.getFullName()
                    cmds.setAttr(name + ".scalePivotY", lock=True)
                    before = self.pivots(name)
                    with self.assertRaises(RuntimeError):
                        node.centerPivot(name + ".vtx[0:1]", fast=fast, check=check)
                    self.assertEqual(self.pivots(name), before)

    def test_invalid_arguments(self):
        """fast・check は bool だけ。面などの点でないコンポーネントは TypeError、空は ValueError。ピボットは変わらない。"""
        node = self.cube()
        name = node.getFullName()
        before = self.pivots(name)
        cases = (
            (TypeError, lambda: node.centerPivot(name + ".vtx[0]", fast=1)),
            (TypeError, lambda: node.centerPivot(name + ".vtx[0]", check=1)),
            (TypeError, lambda: node.centerPivot(name + ".f[0]")),
            (TypeError, lambda: node.centerPivot(name + ".f[0]", fast=True)),
            (TypeError, lambda: node.centerPivot(name + ".vtx[0]", True)),
            (ValueError, lambda: node.centerPivot([])),
            (ValueError, lambda: node.centerPivot([], fast=True)),
        )
        for error, call in cases:
            with self.subTest(error=error.__name__), self.assertRaises(error):
                call()
            self.assertEqual(self.pivots(name), before)


class PivotTranslationTest(_SpecCase):
    """getPivot(translation=True)・setPivot(translation=True) は rotatePivotTranslate・scalePivotTranslate を読み書きする。"""

    def setUp(self):
        super().setUp()
        self.name_ = self.make("transform", "pivotTranslate")
        cmds.setAttr(self.name_ + ".rotatePivotTranslate", 1, 2, 3)
        cmds.setAttr(self.name_ + ".scalePivotTranslate", 4, 5, 6)
        self.node = Node(self.name_)

    def test_get_matches_attributes(self):
        for kind, attribute in (("rotate", "rotatePivotTranslate"), ("scale", "scalePivotTranslate")):
            with self.subTest(kind=kind):
                value = self.node.getPivot(kind=kind, translation=True)
                self.assertIsInstance(value, mlib.Vector)
                self.assertSequenceAlmostEqual(tuple(value), cmds.getAttr(self.name_ + "." + attribute)[0])
        self.assertSequenceAlmostEqual(tuple(self.node.getPivot(translation=True)), (1, 2, 3))
        # translation=False(既定)はピボットそのもの(Translate)。
        self.assertIsInstance(self.node.getPivot(), mlib.Translate)
        self.assertSequenceAlmostEqual(tuple(self.node.getPivot()), tuple(om2.MFnTransform(self.node.mpath()).rotatePivot(om2.MSpace.kPreTransform))[:3])

    def test_set_writes_only_the_translation_and_undoes_once(self):
        for kind, attribute, other in (("rotate", "rotatePivotTranslate", "scalePivotTranslate"), ("scale", "scalePivotTranslate", "rotatePivotTranslate")):
            with self.subTest(kind=kind):
                before = cmds.getAttr(self.name_ + "." + attribute)[0]
                untouched = cmds.getAttr(self.name_ + "." + other)[0]
                pivot = cmds.getAttr(self.name_ + ".rotatePivot")[0]
                cmds.flushUndo()
                self.assertIsNone(self.node.setPivot((7, 8, 9), kind=kind, translation=True))
                self.assertSequenceAlmostEqual(cmds.getAttr(self.name_ + "." + attribute)[0], (7, 8, 9))
                self.assertEqual(cmds.getAttr(self.name_ + "." + other)[0], untouched)
                self.assertEqual(cmds.getAttr(self.name_ + ".rotatePivot")[0], pivot)
                cmds.undo()
                self.assertUndoEmpty()
                self.assertEqual(cmds.getAttr(self.name_ + "." + attribute)[0], before)

    def test_exclusive_arguments(self):
        """translation=True は preserve・fast と同時に指定できない(TypeError)。値は変わらない。"""
        before = (cmds.getAttr(self.name_ + ".rotatePivotTranslate")[0], cmds.getAttr(self.name_ + ".scalePivotTranslate")[0])
        cases = (
            ("preserve True", lambda: self.node.setPivot((7, 8, 9), translation=True, preserve=True)),
            ("preserve False", lambda: self.node.setPivot((7, 8, 9), translation=True, preserve=False)),
            ("fast True", lambda: self.node.setPivot((7, 8, 9), translation=True, fast=True)),
            ("translation int", lambda: self.node.setPivot((7, 8, 9), translation=1)),
            ("get translation int", lambda: self.node.getPivot(translation=1)),
        )
        for label, call in cases:
            with self.subTest(label), self.assertRaises(TypeError):
                call()
            self.assertEqual((cmds.getAttr(self.name_ + ".rotatePivotTranslate")[0], cmds.getAttr(self.name_ + ".scalePivotTranslate")[0]), before)
        for kind in ("both", "pivot"):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.node.getPivot(kind=kind, translation=True)


if __name__ == "__main__":
    unittest.main()
