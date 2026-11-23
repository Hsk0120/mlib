"""ピボット補正と相対シアーの値・空間・Undoを確認する。"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class CompensationTest(NamespaceCase):
    def test_pivot_translation_spaces_and_undo(self):
        parent = mlib.Node(self.make(text="parent"))
        parent.setRotate((12, 33, 8))
        parent.setScale((2, 3, 4))
        child = mlib.Node(self.make(text="child", parent=str(parent)))
        child.setRotate((25, -10, 40))
        child.setScale((1.5, 0.5, 2))
        child.getPlug("rotateAxis").set((15, 20, 30))
        child.setShear((0.2, 0.1, 0.4))
        for kind in ("rotate", "scale"):
            for world in (False, True):
                with self.subTest(kind=kind, world=world):
                    plug = child.getPlug(kind + "PivotTranslate")
                    plug.set((0, 0, 0))
                    self.flushUndo()
                    self.assertIsNone(child.setPivot((2, 4, 6), worldSpace=world, kind=kind, translation=True))
                    self.assertSequenceAlmostEqual(child.getPivot(ws=world, kind=kind, translation=True), (2, 4, 6))
                    cmds.undo()
                    self.assertSequenceAlmostEqual(plug.get(), (0, 0, 0))
                    self.assertUndoEmpty()
                    cmds.redo()
                    self.assertSequenceAlmostEqual(child.getPivot(ws=world, kind=kind, translation=True), (2, 4, 6))

    def test_compensation_offset_parent_and_joint(self):
        parent = mlib.Node(self.make(text="parent"))
        parent.setRotate((12, 33, 8))
        parent.setScale((2, 3, 4))
        offset = om2.MTransformationMatrix()
        offset.setRotation(om2.MEulerRotation(0.2, 0.4, 0.6))
        offset.setScale((0.8, 1.2, 2), om2.MSpace.kTransform)
        for node_type in ("transform", "joint"):
            node = mlib.Node(self.make(node_type, text=node_type, parent=str(parent)))
            node.setRotate((25, -10, 40))
            node.getPlug("rotateAxis").set((15, 20, 30))
            if node_type == "joint":
                node.getPlug("jointOrient").set((10, 20, 30))
            node.getPlug("offsetParentMatrix").set(offset.asMatrix())
            for inherits in (True, False):
                node.getPlug("inheritsTransform").set(inherits)
                for kind in ("rotate", "scale"):
                    with self.subTest(node_type=node_type, inherits=inherits, kind=kind):
                        node.setPivot((2, 4, 6), worldSpace=True, kind=kind, translation=True)
                        self.assertSequenceAlmostEqual(node.getPivot(ws=True, kind=kind, translation=True), (2, 4, 6))

    def test_shear_by_matches_function_set(self):
        node = mlib.Node(self.make(text="value"))
        reference = mlib.Node(self.make(text="reference"))
        node.setShear((0.2, 0.4, 0.8))
        reference.setShear((0.2, 0.4, 0.8))
        self.flushUndo()
        self.assertIsNone(node.setShear((2, 3, 0.5), relative=True))
        om2.MFnTransform(reference.mpath()).shearBy((2, 3, 0.5))
        self.assertSequenceAlmostEqual(node.getShear(), reference.getShear())
        cmds.undo()
        self.assertSequenceAlmostEqual(node.getShear(), (0.2, 0.4, 0.8))
        self.assertUndoEmpty()

    def test_pivot_vectors_match_world_displacement(self):
        parent = mlib.Node(self.make(text="parent"))
        parent.setScale((2, 3, 4))
        parent.setRotate((12, 33, 8))
        for node_type in ("transform", "joint"):
            node = mlib.Node(self.make(node_type, text=node_type, parent=str(parent)))
            node.setRotate((25, -10, 40))
            node.getPlug("rotateAxis").set((15, 20, 30))
            if node_type == "joint":
                node.getPlug("jointOrient").set((10, 20, 30))
                parent.getPlug("scale").connect(node.getPlug("inverseScale"))
            for compensated in (True, False):
                if node_type == "joint":
                    node.getPlug("segmentScaleCompensate").set(compensated)
                for kind in ("rotate", "scale"):
                    with self.subTest(node_type=node_type, compensated=compensated, kind=kind):
                        node.setPivot((0, 0, 0), kind=kind, translation=True)
                        before = tuple(node.getMatrix(worldSpace=True))[12:15]
                        node.setPivot((1, 2, 3), kind=kind, translation=True)
                        after = tuple(node.getMatrix(worldSpace=True))[12:15]
                        self.assertSequenceAlmostEqual(node.getPivot(worldSpace=True, kind=kind, translation=True), tuple(b - a for a, b in zip(before, after)))
                        node.setPivot((2, 4, 6), worldSpace=True, kind=kind, translation=True)
                        self.assertSequenceAlmostEqual(node.getPivot(worldSpace=True, kind=kind, translation=True), (2, 4, 6))

    def test_invalid_inputs_leave_channels(self):
        node = mlib.Node(self.make())
        self.flushUndo()
        with self.assertRaises(ValueError):
            node.setPivot((1, 2, 3), kind="both", translation=True)
        with self.assertRaises(TypeError):
            node.getPivot(True, ws=False, translation=True)
        with self.assertRaises(ValueError):
            node.setShear((1, float("nan"), 2), relative=True)
        self.assertUndoEmpty()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
