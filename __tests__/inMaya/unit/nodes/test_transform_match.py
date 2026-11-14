"""``mlib.nodes.transform`` のテスト。

- 共通メソッドのMaya結果・単位・Undo/Redoを検証する。
- 名前空間・選択・matchTransform の通常経路と、om2 へ置き換えた読み取りを cmds と突き合わせる。
"""

import sys
import unittest
import uuid

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class CommonMethodsTest(unittest.TestCase):
    def setUp(self):
        self.namespace = "mlibCommon_" + uuid.uuid4().hex
        cmds.namespace(add=self.namespace)

    def tearDown(self):
        cmds.namespace(removeNamespace=self.namespace, deleteNamespaceContent=True)

    def create(self, name, type="transform", **kwargs):
        return mlib.createNode(type, name=self.namespace + ":" + name, **kwargs)

    def test_center_pivot_preserves_geometry_and_undo(self):
        name = cmds.polyCube(name=self.namespace + ":pivotMesh")[0]
        node = mlib.getNode(name)
        cmds.move(3, 1, -2, name + ".vtx[*]", relative=True)
        cmds.setAttr(name + ".rotateY", 30)
        cmds.setAttr(name + ".scaleX", 2)
        points = cmds.xform(name + ".vtx[*]", query=True, translation=True, worldSpace=True)
        before = cmds.xform(name, query=True, pivots=True)
        self.assertIs(node.centerPivot(), node)
        after = cmds.xform(name, query=True, pivots=True)
        self.assertNotEqual(after, before)
        for a, b in zip(points, cmds.xform(name + ".vtx[*]", query=True, translation=True, worldSpace=True)):
            self.assertAlmostEqual(a, b)
        cmds.undo()
        self.assertEqual(cmds.xform(name, query=True, pivots=True), before)
        cmds.redo()
        self.assertEqual(cmds.xform(name, query=True, pivots=True), after)

    def test_match_transform_matches_maya_and_undo(self):
        parent = self.create("parent")
        parent.getPlug("translate").set((4, 2, -1))
        target = self.create("target")
        actual = self.create("actual", parent=parent.getFullName())
        expected = self.create("expected", parent=parent.getFullName())
        target.getPlug("translate").set((10, 3, -5))
        target.getPlug("rotate").set((20, 30, 10))
        target.getPlug("scale").set((2, 3, 4))
        before = cmds.xform(actual.getFullName(), query=True, matrix=True, worldSpace=True)
        cmds.matchTransform(expected.getFullName(), target.getFullName(), position=True, rotation=True, scale=True, pivots=False)
        self.assertIs(actual.matchTransform(target), actual)
        after = cmds.xform(actual.getFullName(), query=True, matrix=True, worldSpace=True)
        for a, b in zip(after, cmds.xform(expected.getFullName(), query=True, matrix=True, worldSpace=True)):
            self.assertAlmostEqual(a, b)
        cmds.undo()
        for a, b in zip(before, cmds.xform(actual.getFullName(), query=True, matrix=True, worldSpace=True)):
            self.assertAlmostEqual(a, b)
        cmds.redo()
        for a, b in zip(after, cmds.xform(actual.getFullName(), query=True, matrix=True, worldSpace=True)):
            self.assertAlmostEqual(a, b)

    def test_match_position_only_and_noop(self):
        actual, target = self.create("actual"), self.create("target")
        cmds.setAttr(actual.getFullName() + ".rotate", 15, 0, 0)
        target.getPlug("translate").set((7, 8, 9))
        actual.matchTransform(target.getFullName(), rotation=False, scale=False)
        self.assertEqual(tuple(actual.getPlug("translate").get()), (7, 8, 9))
        self.assertAlmostEqual(actual.getPlug("rotateX").get(), 15)
        undo_name = cmds.undoInfo(query=True, undoName=True)
        actual.matchTransform(target, position=False, rotation=False, scale=False)
        self.assertEqual(cmds.undoInfo(query=True, undoName=True), undo_name)
        with self.assertRaises(TypeError):
            actual.matchTransform(self.create("network", type="network"))

    def skin(self):
        joints = [self.create("joint" + str(i), type="joint") for i in range(3)]
        mesh = cmds.polyCube(name=self.namespace + ":mesh")[0]
        skin = mlib.getNode(cmds.skinCluster([j.getFullName() for j in joints], mesh)[0])
        return joints, mlib.getNode(mesh), skin


class _CommonCase(NamespaceCase):
    PREFIX = "mlibSpecCommonEdits_"

    def setUp(self):
        super().setUp()
        self.current = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)
        self.relative = cmds.namespace(query=True, relativeNames=True)
        self.selection = cmds.ls(selection=True, long=True)
        cmds.select(clear=True)

    def tearDown(self):
        cmds.namespace(relativeNames=self.relative)
        cmds.namespace(set=self.current if cmds.namespace(exists=self.current) else ":")
        if self.selection:
            cmds.select(self.selection, replace=True)
        else:
            cmds.select(clear=True)
        super().tearDown()

    def namespaces(self, root):
        """root 配下の名前空間を root からの相対名で返す。"""
        names = cmds.namespaceInfo(root, listOnlyNamespaces=True, recurse=True, absoluteName=True) or []
        return sorted(name[len(root) :] for name in names)

    def nodes(self, root):
        """root 配下のノードを root からの相対名で返す。"""
        names = cmds.namespaceInfo(root, listOnlyDependencyNodes=True, recurse=True, absoluteName=True) or []
        return sorted(name[len(root) :] for name in names)


class MatchTransformTest(_CommonCase):
    def scene(self):
        parent = self.make(text="P#")
        cmds.xform(parent, translation=(1, 2, 3), rotation=(10, 20, 30), scale=(1.5, 2, 0.5))
        other = self.make(text="Q#")
        cmds.xform(other, translation=(-2, 1, 4), rotation=(-40, 15, 60), scale=(0.7, 1.3, 1.1))
        source = self.make("transform", "S#", parent=parent)
        target = self.make("transform", "T#", parent=other)
        cmds.xform(source, translation=(0.3, -1, 2), rotation=(5, 70, -20), scale=(1, 2, 3))
        cmds.xform(target, translation=(3, 1, -1), rotation=(45, -30, 80), scale=(2, 0.5, 1.5))
        return source, target

    def snapshot(self, node):
        return (
            cmds.xform(node, query=True, worldSpace=True, matrix=True)
            + cmds.xform(node, query=True, worldSpace=True, rotatePivot=True)
            + cmds.xform(node, query=True, worldSpace=True, scalePivot=True)
        )

    def test_all_false_is_noop(self):
        """全フラグ False は何も変更しない。"""
        source, target = self.scene()
        before = self.snapshot(source)
        mlib.getNode(source).matchTransform(target, position=False, rotation=False, scale=False)
        self.assertEqual(self.snapshot(source), before)

    def test_rejects_non_transform(self):
        """合わせ先が Transform でなければ TypeError。"""
        source, _ = self.scene()
        with self.assertRaises(TypeError):
            mlib.getNode(source).matchTransform(self.make("network", "dg#"))

    def test_normal_undo_once(self):
        """cmds.matchTransform と同じ結果で、Undo 1 回で戻る。"""
        source, target = self.scene()
        before = self.snapshot(source)
        cmds.flushUndo()
        mlib.getNode(source).matchTransform(target, pivots=True)
        result = self.snapshot(source)
        cmds.undo()
        self.assertSequenceAlmostEqual(self.snapshot(source), before)
        cmds.matchTransform(source, target, position=True, rotation=True, scale=True, pivots=True)
        self.assertSequenceAlmostEqual(result, self.snapshot(source), places=6)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
