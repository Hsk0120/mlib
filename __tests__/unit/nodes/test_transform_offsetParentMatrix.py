"""別TransformのMatrixをoffsetParentMatrixへ設定する経路を検証する。

あわせて次も確かめる。

- DAG・Transform・アニメーションカーブ・DG の照会と編集の契約を固定する。
"""

import sys
import unittest

from maya.api.OpenMaya import MSpace
import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.cmds.bakeResults import bakeResults
from mlib.maths import Matrix
from mlib.nodes import AnimCurve
from mlib.plugs.matrixPlug import MatrixPlug
from support.namespaceCase import NamespaceCase


class OffsetParentMatrixTest(unittest.TestCase):
    """テスト用階層だけを作成・破棄する。"""

    def setUp(self):
        self.root = mlib.createNode("transform")
        self.source = mlib.createNode("transform", parent=self.root)
        self.target = mlib.createNode("transform", parent=self.root)

    def tearDown(self):
        cmds.delete(self.root.getFullName())

    def test_matrix_type_copy_undo_and_fast(self):
        self.source.setTranslation((2, 3, 4), at=4)
        self.source.setRotate((.2, .3, .4))
        self.source.setScale((2, 3, 4))
        value = self.source.getMatrix()
        plug = self.target.getPlug("offsetParentMatrix")
        self.assertIsInstance(value, Matrix)
        self.assertIsInstance(plug, MatrixPlug)
        self.assertIs(plug.set(value), plug)
        self.assertIsInstance(plug.get(), Matrix)
        self.assertTrue(plug.get().isEquivalent(value, 1e-9))
        self.assertTrue(self.target.getMatrix().isEquivalent(Matrix(), 1e-9))
        self.assertTrue(self.target.getMatrix(worldSpace=True).isEquivalent(value, 1e-9))
        cmds.undo()
        self.assertTrue(plug.get().isEquivalent(Matrix(), 1e-9))
        cmds.redo()
        self.assertTrue(plug.get().isEquivalent(value, 1e-9))
        plug.set(Matrix(), fast=True)
        self.assertTrue(plug.get().isEquivalent(Matrix(), 1e-9))
        plug.set(value, fast=True)
        self.assertTrue(plug.get().isEquivalent(value, 1e-9))

    def test_world_alignment_preserves_channels(self):
        self.root.setTranslation((10, 20, 30), at=4)
        self.root.setRotate((.1, .2, .3))
        self.root.setScale((2, 3, 4))
        self.source.setTranslation((4, 5, 6), at=4)
        self.target.setTranslation((1, 2, 3), at=4)
        self.target.setRotate((.4, .5, .6))
        local = self.target.getMatrix()
        world = self.source.getMatrix(worldSpace=True)
        offset = local.inverse() * world * self.root.getMatrix(worldSpace=True).inverse()
        self.target.getPlug("offsetParentMatrix").set(offset)
        self.assertTrue(self.target.getMatrix().isEquivalent(local, 1e-9))
        self.assertTrue(self.target.getMatrix(worldSpace=True).isEquivalent(world, 1e-8))

    def test_plug_route_and_multiple_nodes(self):
        """offsetParentMatrix は getPlug("offsetParentMatrix") の get/set でも扱え、専用入口と一致する。"""
        from mlib.decorator import undoChunk
        nodes = [self.source, self.target]
        value = Matrix(translate=(4, 5, 6))
        for name in ("getOffsetParentMatrix", "setOffsetParentMatrix"):
            self.assertTrue(hasattr(self.target, name))
        plug = self.target.getPlug("offsetParentMatrix")
        self.assertIs(plug.set(value), plug)
        self.assertTrue(plug.get().isEquivalent(value))
        cmds.undo()
        self.assertTrue(plug.get().isEquivalent(Matrix()))
        with undoChunk("mlibOffsetParentMatrixTest"):
            for node in nodes:
                node.getPlug("offsetParentMatrix").set(value)
        self.assertTrue(all(node.getPlug("offsetParentMatrix").get().isEquivalent(value) for node in nodes))
        cmds.undo()
        self.assertTrue(all(node.getPlug("offsetParentMatrix").get().isEquivalent(Matrix()) for node in nodes))
        plug.set(value, fast=True)
        self.assertTrue(plug.get().isEquivalent(value))
        cmds.setAttr(self.target.getFullName() + ".offsetParentMatrix", lock=True)
        with self.assertRaises(RuntimeError):
            plug.set(Matrix())


def _world(name):
    """cmds で読むワールドマトリクス。"""
    return cmds.xform(name, query=True, worldSpace=True, matrix=True)


class OffsetParentMatrixDagQueriesTest(NamespaceCase):

    def test_get_set(self):
        """get は offsetParentMatrix を返し、set は通常 Undo 1回、fast は Undo なし。"""
        name = self.make()
        node = mlib.getNode(name)
        self.assertEqual(node.getOffsetParentMatrix(), Matrix())
        value = Matrix(translate=(1, 2, 3))
        self.flushUndo()
        self.assertIs(node.setOffsetParentMatrix(value), node)
        self.assertSequenceAlmostEqual(cmds.getAttr(name + ".offsetParentMatrix"), list(value))
        self.assertIsInstance(node.getOffsetParentMatrix(), Matrix)
        self.assertUndoesInOneStep(lambda: self.assertEqual(node.getOffsetParentMatrix(), Matrix()), lambda: None)
        node.setOffsetParentMatrix(list(value), fast=True)
        self.assertUndoEmpty()
        self.assertEqual(node.getOffsetParentMatrix(), value)
        self.assertRaises(ValueError, node.setOffsetParentMatrix, [1, 2])
        self.assertRaises(TypeError, node.setOffsetParentMatrix, value, fast=1)

    def assertFrozen(self, name, attributes):
        for attribute, expected in attributes:
            self.assertSequenceAlmostEqual(cmds.getAttr(name + "." + attribute)[0], expected)

    def test_freeze_transform(self):
        """ピボット・rotateAxis・既存の offsetParentMatrix・親があってもワールドを保ち、Undo 1回で戻る。"""
        parent = self.make(text="parent")
        cmds.xform(parent, translation=(1, 2, 3), rotation=(10, 20, 30), scale=(2, 2, 2))
        name = self.make(text="child", parent=parent)
        cmds.xform(name, translation=(4, -1, 2), rotation=(30, 45, 60), scale=(1, 2, 3), shear=(0.1, 0, 0.2))
        cmds.setAttr(name + ".rotateAxis", 5, 10, 15)
        cmds.setAttr(name + ".rotateOrder", 3)
        cmds.setAttr(name + ".rotatePivot", 0.5, 0.2, 0.1)
        cmds.setAttr(name + ".scalePivot", -0.3, 0.4, 0.0)
        offset = om2.MTransformationMatrix()
        offset.setRotation(om2.MEulerRotation(0.1, 0, 0))
        offset.setTranslation(om2.MVector(0, 1, 0), om2.MSpace.kTransform)
        cmds.setAttr(name + ".offsetParentMatrix", *offset.asMatrix(), type="matrix")
        world = _world(name)
        self.flushUndo()
        node = mlib.getNode(name)
        self.assertIs(node.freezeToOffsetParent(), node)
        self.assertSequenceAlmostEqual(_world(name), world)
        self.assertFrozen(name, (("translate", (0, 0, 0)), ("rotate", (0, 0, 0)), ("scale", (1, 1, 1)),
                                 ("shear", (0, 0, 0)), ("rotateAxis", (5, 10, 15))))
        self.assertUndoesInOneStep(lambda: self.assertSequenceAlmostEqual(
            cmds.getAttr(name + ".translate")[0], (4, -1, 2)), lambda: None)
        self.assertSequenceAlmostEqual(_world(name), world)

    def test_freeze_joint(self):
        """Joint は jointOrient も0にし、segmentScaleCompensate の親スケールがあってもワールドを保つ。"""
        parent = self.make("joint", "parentJnt")
        cmds.setAttr(parent + ".scale", 2, 1, 1)
        name = self.make("joint", "childJnt", parent=parent)
        cmds.setAttr(name + ".translate", 3, 1, 0)
        cmds.setAttr(name + ".rotate", 10, 20, 30)
        cmds.setAttr(name + ".jointOrient", 0, 0, 45)
        world = _world(name)
        mlib.getNode(name).freezeToOffsetParent()
        self.assertSequenceAlmostEqual(_world(name), world)
        self.assertFrozen(name, (("translate", (0, 0, 0)), ("rotate", (0, 0, 0)), ("jointOrient", (0, 0, 0))))

    def test_freeze_rejects_locked_or_keyed(self):
        """ロック・キーのあるチャンネルは何も変えずに RuntimeError。"""
        name = self.make()
        cmds.setAttr(name + ".translateX", 2)
        node = mlib.getNode(name)
        cmds.setAttr(name + ".rotateY", lock=True)
        self.assertRaises(RuntimeError, node.freezeToOffsetParent)
        cmds.setAttr(name + ".rotateY", lock=False)
        cmds.setKeyframe(name, attribute="scaleZ", time=1, value=1)
        self.assertRaises(RuntimeError, node.freezeToOffsetParent)
        self.assertEqual(cmds.getAttr(name + ".translateX"), 2)
        self.assertEqual(node.getOffsetParentMatrix(), Matrix())


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
