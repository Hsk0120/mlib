"""DAG取得の統合とTransformの通常・高速更新を検証する。"""

import unittest
from unittest import mock

import maya.cmds as cmds

import mlib


class ConsolidatedDagTests(unittest.TestCase):
    """隔離シーンで検索条件、UndoとOpenMaya更新の差を確認する。"""

    def setUp(self):
        """テスト専用の新規シーンを用意する。"""
        cmds.file(new=True, force=True)
        cmds.undoInfo(state=True)

    def tearDown(self):
        """検証で作成したシーンを破棄する。"""
        cmds.file(new=True, force=True)

    def test_children_filters_orders_and_leaves(self):
        """直接子と子孫・Shape・中間・葉・自身の条件を区別する。"""
        root = mlib.createNode("transform", name="queryRoot")
        a = mlib.createNode("transform", name="queryA", parent=root)
        mlib.createNode("transform", name="queryB", parent=root)
        c = mlib.createNode("transform", name="queryC", parent=a)
        shape = mlib.createNode("mesh", name="queryShape", parent=a)

        def names(nodes):
            return [node.getName() for node in nodes]

        self.assertEqual(names(root.getChildren()), ["queryA", "queryB"])
        self.assertEqual(names(root.getChildren(allDescendents=True)), ["queryA", "queryC", "queryB"])
        self.assertEqual(names(root.getChildren(allDescendents=True, sortBy="breadthFirst")), ["queryA", "queryB", "queryC"])
        self.assertEqual(names(root.getChildren(leaves=True, includeSelf=True)), ["queryC", "queryB"])
        self.assertEqual(c.getChildren(leaves=True, includeSelf=True), [c])
        self.assertEqual(c.getChildren(leaves=True), [])
        self.assertEqual(a.getShape(all=True), [shape])
        self.assertEqual(shape.getChildren(), [])
        shape.getPlug("intermediateObject").set(True)
        self.assertEqual(a.getShape(all=True), [])
        self.assertEqual(a.getShape(intermediates=True, all=True), [shape])
        self.assertEqual(names(a.getChildren(shapes=True, intermediates=True)), ["queryC", "queryShape"])
        with self.assertRaises(ValueError):
            root.getChildren(shapes=True, leaves=True)
        with self.assertRaises(ValueError):
            root.getChildren(sortBy="invalid")

    def test_children_preserve_instance_path(self):
        """同じノードを別親から探索しても各インスタンスのパスを保持する。"""
        first = cmds.createNode("transform", name="firstRoot")
        second = cmds.createNode("transform", name="secondRoot")
        child = cmds.createNode("transform", name="sharedChild", parent=first)
        cmds.parent(child, second, add=True)
        a = mlib.getNode(first).getChildren()[0]
        b = mlib.getNode(second).getChildren()[0]
        self.assertEqual(a.mnode(), b.mnode())
        self.assertNotEqual(a.getName(full=True), b.getName(full=True))
        self.assertEqual(a.getParent().getName(full=True), "|firstRoot")
        self.assertEqual(b.getParent().getName(full=True), "|secondRoot")

    def test_pivot_fast_matches_cmds_and_read_is_api_only(self):
        """非一様スケールと親を含むピボット設定を通常経路と比較する。"""
        parent = mlib.createNode("transform", name="pivotParent")
        parent.setTranslation((2, 3, 4))
        parent.setRotate((0.2, 0.3, 0.4))
        parent.setScale((1.5, 2, 3))
        for world in (False, True):
            for kind in ("rotate", "scale", "both"):
                for preserve in (False, True):
                    nodes = [mlib.createNode("transform", parent=parent) for _ in range(2)]
                    for node in nodes:
                        node.setTranslation((1, 2, 3))
                        node.setRotate((0.3, 0.1, 0.5))
                        node.setScale((2, 3, 4))
                    nodes[0].setPivot((4, 5, 6), worldSpace=world, kind=kind, preserve=preserve)
                    cmds.flushUndo()
                    with mock.patch.object(cmds, "xform", side_effect=AssertionError("cmds xform used")):
                        nodes[1].setPivot((4, 5, 6), worldSpace=world, kind=kind, preserve=preserve, fast=True)
                        for pivot_kind in ("rotate", "scale"):
                            expected = nodes[0].getPivot(worldSpace=world, kind=pivot_kind)
                            actual = nodes[1].getPivot(worldSpace=world, kind=pivot_kind)
                            self.assertTrue(actual.isEquivalent(expected, 1e-8), (world, kind, preserve, pivot_kind, tuple(actual), tuple(expected)))
                    self.assertTrue(nodes[0].getMatrix(worldSpace=True).isEquivalent(nodes[1].getMatrix(worldSpace=True), 1e-8))
                    self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))

    def test_pivot_regular_undo_and_fast_lock_validation(self):
        """通常のピボットはUndoでき、高速経路もロックを迂回しない。"""
        node = mlib.createNode("transform")
        initial = node.getPivot()
        node.setPivot((3, 4, 5))
        cmds.undo()
        self.assertTrue(node.getPivot().isEquivalent(initial))
        node.getPlug("rotatePivotX").setFlags(locked=True)
        with self.assertRaises(RuntimeError):
            node.setPivot((1, 2, 3), fast=True, check=True)
        self.assertTrue(node.getPivot().isEquivalent(initial))

    def test_reparent_fast_keeps_world_matrix_and_records_no_undo(self):
        """高速再親付けで非一様スケール・回転・ピボットを含む姿勢を保つ。"""
        old = mlib.createNode("transform", name="oldParent")
        new = mlib.createNode("transform", name="newParent")
        old.setTranslation((1, 2, 3))
        old.setRotate((0.3, 0.1, 0.7))
        old.setScale((2, 3, 4))
        new.setTranslation((-4, 5, 2))
        new.setRotate((0.1, 0.6, 0.2))
        new.setScale((3, 2, 1))
        node = mlib.createNode("transform", name="reparentChild", parent=old)
        node.setTranslation((3, 1, 2))
        node.setRotate((0.4, 0.2, 0.1))
        node.setPivot((1, 2, 1), kind="both")
        initial = node.getMatrix(worldSpace=True)
        cmds.flushUndo()
        with mock.patch.object(cmds, "parent", side_effect=AssertionError("cmds parent used")):
            self.assertIsNone(node.setParent(new, fast=True))
            self.assertEqual(node.getParent(), new)
            self.assertTrue(node.getMatrix(worldSpace=True).isEquivalent(initial, 1e-8))
            node.setParent(None, fast=True)
            self.assertIsNone(node.getParent())
            self.assertTrue(node.getMatrix(worldSpace=True).isEquivalent(initial, 1e-8))
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))

    def test_reparent_relative_and_joint_rejection(self):
        """relativeのローカル保持とJoint更新前拒否を確認する。"""
        parent = mlib.createNode("transform")
        parent.setTranslation((5, 6, 7))
        node = mlib.createNode("transform")
        node.setTranslation((1, 2, 3))
        local = node.getMatrix()
        node.setParent(parent, relative=True, fast=True)
        self.assertTrue(node.getMatrix().isEquivalent(local))
        joint = mlib.createNode("joint")
        with self.assertRaises(NotImplementedError):
            joint.setParent(parent, fast=True)
        self.assertIsNone(joint.getParent())

    def test_center_pivot_fast_matches_standard(self):
        """非対称形状のバウンディング中心を通常経路と比較する。"""
        parent = mlib.createNode("transform")
        parent.setTranslation((3, 4, 5))
        parent.setRotate((0.2, 0.5, 0.7))
        first = mlib.getNode(cmds.polyCube(constructionHistory=False)[0])
        cmds.move(5, 2, 8, first.getName(full=True) + ".vtx[0]", relative=True)
        second = mlib.getNode(cmds.duplicate(first.getName(full=True))[0])
        for node in (first, second):
            node.setParent(parent, relative=True)
            node.setTranslation((1, 2, 3))
            node.setRotate((0.3, 0.2, 0.4))
            node.setScale((2, 3, 4))
        first.centerPivot()
        cmds.flushUndo()
        with mock.patch.object(cmds, "xform", side_effect=AssertionError("cmds xform used")):
            second.centerPivot(fast=True)
        self.assertTrue(first.getPivot(worldSpace=True).isEquivalent(second.getPivot(worldSpace=True), 1e-8))
        self.assertTrue(first.getMatrix(worldSpace=True).isEquivalent(second.getMatrix(worldSpace=True), 1e-8))
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))

    def test_constraint_fast_delete_uses_api_and_keeps_sources(self):
        """高速削除は拘束元を残し、問い合わせも標準コマンドへ戻らない。"""
        source = mlib.createNode("transform")
        driven = mlib.createNode("transform")
        constraint = driven.addConstraint(source, type="point")
        name = constraint.getName(full=True)
        cmds.flushUndo()
        with mock.patch.object(cmds, "listConnections", side_effect=AssertionError("cmds query used")), mock.patch.object(
            cmds, "delete", side_effect=AssertionError("cmds delete used")
        ):
            self.assertEqual(driven.deleteConstraints(fast=True), [name])
        self.assertFalse(constraint.isValid())
        self.assertTrue(source.isValid())
        self.assertTrue(driven.isValid())
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))

    def test_intermediate_fast_delete_keeps_input_history(self):
        """未使用中間Shapeだけを削除し、上流履歴とTransformを維持する。"""
        target = mlib.createNode("transform")
        shape = mlib.createNode("mesh", parent=target)
        shape.getPlug("intermediateObject").set(True)
        history = mlib.createNode("polyCube")
        history.getPlug("output").connectTo(shape.getPlug("inMesh"))
        cmds.flushUndo()
        self.assertIsNone(target.deleteUnusedIntermediateShapes(fast=True))
        self.assertFalse(shape.isValid())
        self.assertTrue(target.isValid())
        self.assertTrue(history.isValid())
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))

    def test_reparent_fast_matches_normal_with_pivots_and_rotate_axis(self):
        """ピボット・rotateAxis・回転順序・スケールした親があっても、fastと通常で同じワールドの姿勢になる。

        通常(Mayaのparent)はピボットの値を動かし、fastはピボットを保ってtranslateで合わせる。
        回転・スケール・シアーは同じ値になる。
        """
        results = {}
        for fast in (False, True):
            cmds.file(new=True, force=True)
            old = cmds.createNode("transform", name="oldParent")
            cmds.setAttr(old + ".t", 1, 2, 3)
            cmds.setAttr(old + ".r", 20, 30, 40)
            new = cmds.createNode("transform", name="newParent")
            cmds.setAttr(new + ".t", -2, 1, 5)
            cmds.setAttr(new + ".r", 15, -25, 35)
            cmds.setAttr(new + ".s", 2, 2, 2)
            child = cmds.createNode("transform", name="child", parent=old)
            cmds.setAttr(child + ".rotateOrder", 3)
            cmds.setAttr(child + ".t", 3, -1, 2)
            cmds.setAttr(child + ".r", 10, 50, -20)
            cmds.setAttr(child + ".s", 1.5, 0.5, 2)
            cmds.setAttr(child + ".rotateAxis", 5, 10, 15)
            cmds.setAttr(child + ".rotatePivot", 0.5, 0.2, 0.1)
            cmds.setAttr(child + ".scalePivot", 0.1, 0.3, -0.2)
            cmds.setAttr(child + ".rotatePivotTranslate", 0.2, 0.0, 0.1)
            world = cmds.getAttr(child + ".worldMatrix")
            cmds.flushUndo()
            node = mlib.getNode(child)
            self.assertIsNone(node.setParent(mlib.getNode(new), fast=fast))
            path = node.getName(full=True)
            self.assertEqual(cmds.listRelatives(path, parent=True), ["newParent"])
            for actual, expected in zip(cmds.getAttr(path + ".worldMatrix"), world):
                self.assertAlmostEqual(actual, expected, places=6)
            self.assertEqual(cmds.undoInfo(query=True, undoQueueEmpty=True), fast)
            results[fast] = [value for attr in ("r", "s", "sh", "rotateAxis") for value in cmds.getAttr(f"{path}.{attr}")[0]]
            if fast:
                pivots = {"rotatePivot": (0.5, 0.2, 0.1), "scalePivot": (0.1, 0.3, -0.2), "rotatePivotTranslate": (0.2, 0.0, 0.1)}
                for attr, expected in pivots.items():
                    for actual, wanted in zip(cmds.getAttr(f"{path}.{attr}")[0], expected):
                        self.assertAlmostEqual(actual, wanted, places=9)
        for normal, quick in zip(results[False], results[True]):
            self.assertAlmostEqual(quick, normal, places=5)

    def test_reparent_fast_rejects_locked_channel_before_change(self):
        """check=Trueなら、書き込めないチャンネルがあれば、親を変える前に、これまでと同じ文言で拒否する。"""
        parent = cmds.createNode("transform", name="lockedTarget")
        cmds.setAttr(parent + ".t", 1, 2, 3)
        for case in ("lockChild", "lockParent", "connectChild"):
            with self.subTest(case=case):
                child = cmds.createNode("transform", name="lockedChild#")
                if case == "lockChild":
                    cmds.setAttr(child + ".ry", lock=True)
                elif case == "lockParent":
                    cmds.setAttr(child + ".s", lock=True)
                else:
                    cmds.connectAttr(parent + ".tx", child + ".tz")
                cmds.flushUndo()
                with self.assertRaises(RuntimeError) as caught:
                    mlib.getNode(child).setParent(mlib.getNode(parent), fast=True, check=True)
                self.assertIn("アトリビュートがロックされているか、接続されています", str(caught.exception))
                self.assertIsNone(cmds.listRelatives(child, parent=True))
                self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))

    def test_reparent_fast_without_pivots_keeps_world_matrix(self):
        """ピボットが無いときは分解した値をそのまま書く。姿勢・回転順序・rotateAxisは保ち、Undoに残さない。"""
        cases = {
            "plain": {"s": (1.5, 0.5, 2.0), "parentScale": (2.0, 2.0, 2.0)},
            "negativeScale": {"s": (-1.0, 1.0, 1.0), "parentScale": (1.0, 1.0, 1.0)},
            "mirroredParent": {"s": (1.0, 2.0, 1.0), "parentScale": (-1.0, 1.0, 1.0)},
            "shearFromParent": {"s": (1.0, 1.0, 1.0), "parentScale": (1.0, 3.0, 0.5)},
        }
        for label, values in cases.items():
            for to_world in (False, True):
                with self.subTest(case=label, toWorld=to_world):
                    cmds.file(new=True, force=True)
                    old = cmds.createNode("transform", name="oldParent")
                    cmds.setAttr(old + ".t", 1, 2, 3)
                    cmds.setAttr(old + ".r", 20, 30, 40)
                    new = cmds.createNode("transform", name="newParent")
                    cmds.setAttr(new + ".t", -2, 1, 5)
                    cmds.setAttr(new + ".r", 15, -25, 35)
                    cmds.setAttr(new + ".s", *values["parentScale"])
                    child = cmds.createNode("transform", name="child", parent=old)
                    cmds.setAttr(child + ".rotateOrder", 4)
                    cmds.setAttr(child + ".t", 3, -1, 2)
                    cmds.setAttr(child + ".r", 10, 50, -20)
                    cmds.setAttr(child + ".s", *values["s"])
                    cmds.setAttr(child + ".rotateAxis", 5, 10, 15)
                    world = cmds.getAttr(child + ".worldMatrix")
                    cmds.flushUndo()
                    node = mlib.getNode(child)
                    node.setParent(None if to_world else mlib.getNode(new), fast=True)
                    path = node.getName(full=True)
                    self.assertEqual(cmds.listRelatives(path, parent=True), None if to_world else ["newParent"])
                    for actual, expected in zip(cmds.getAttr(path + ".worldMatrix"), world):
                        self.assertAlmostEqual(actual, expected, places=6)
                    self.assertEqual(cmds.getAttr(path + ".rotateOrder"), 4)
                    for actual, expected in zip(cmds.getAttr(path + ".rotateAxis")[0], (5, 10, 15)):
                        self.assertAlmostEqual(actual, expected, places=9)
                    for attr in ("rotatePivot", "scalePivot", "rotatePivotTranslate", "scalePivotTranslate"):
                        self.assertEqual(cmds.getAttr(f"{path}.{attr}")[0], (0.0, 0.0, 0.0))
                    self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))


if __name__ == "__main__":
    unittest.main()
