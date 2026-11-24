"""rotateAxisの変更で現在の姿勢を保つ指定を検証する。"""

import math
import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class TransformRotateAxisTest(NamespaceCase):
    def test_preserves_transform_and_joint_all_orders_and_undo(self):
        cmds.currentUnit(angle="deg", linear="cm")
        for kind in ("transform", "joint"):
            for order in range(6):
                with self.subTest(kind=kind, order=order):
                    node = self._node(kind, order)
                    matrix = list(node.getMatrix(worldSpace=True))
                    before = self._state(node)
                    self.flushUndo()
                    self.assertIsNone(node.setQuaternion(self._rotation(), rotate=False, jointOrient=False, preserve=True))
                    self.assertSequenceAlmostEqual(node.getMatrix(worldSpace=True), matrix)
                    self.assertSameRotation(node.getQuaternion(rotateAxis=True, rotate=False, jointOrient=False), self._rotation())
                    after = self._state(node)
                    self.assertNotEqual(before, after)
                    cmds.undo()
                    for actual, expected in zip(self._state(node), before):
                        self.assertSequenceAlmostEqual(actual[0], expected[0])
                    self.assertUndoEmpty()
                    cmds.redo()
                    for actual, expected in zip(self._state(node), after):
                        self.assertSequenceAlmostEqual(actual[0], expected[0])

    def test_fast_matches_normal_without_undo(self):
        for kind in ("transform", "joint"):
            with self.subTest(kind=kind):
                node = self._node(kind, 4)
                matrix = list(node.getMatrix(worldSpace=True))
                node.setQuaternion(self._rotation(), r=False, jo=False, preserve=True)
                after = self._state(node)
                cmds.undo()
                self.flushUndo()
                state = cmds.undoInfo(query=True, state=True)
                node.setQuaternion(self._rotation(), r=False, jo=False, preserve=True, fast=True)
                self.assertSequenceAlmostEqual(node.getMatrix(worldSpace=True), matrix)
                for actual, expected in zip(self._state(node), after):
                    self.assertSequenceAlmostEqual(actual[0], expected[0])
                self.assertEqual(cmds.undoInfo(query=True, state=True), state)
                self.assertUndoEmpty()

    def test_angle_ui_units_and_default_behavior(self):
        node = self._node()
        cmds.currentUnit(angle="rad")
        before = list(node.getMatrix(worldSpace=True))
        node.setQuaternion(self._rotation(), r=False, jo=False, preserve=True)
        self.assertSequenceAlmostEqual(node.getMatrix(worldSpace=True), before)
        cmds.undo()
        node.setQuaternion(self._rotation(), r=False, jo=False)
        self.assertGreater(max(abs(a - b) for a, b in zip(node.getMatrix(worldSpace=True), before)), 0.01)

    def test_get_only_and_invalid_options_do_not_write(self):
        node = self._node()
        before = self._state(node)
        self.flushUndo()
        result = node.setQuaternion(self._rotation(), r=False, jo=False, preserve=True, get=True, safe=True)
        self.assertIsInstance(result, mlib.EulerRotate)
        self.assertSameRotation(result.asQuaternion(), self._rotation())
        for flags, error in (
            ({"preserve": 1}, TypeError),
            ({"preserve": True}, ValueError),
            ({"preserve": True, "r": False, "jo": False, "safe": True}, ValueError),
            ({"preserve": True, "r": False, "jo": False, "safe": 1}, TypeError),
            ({"preserve": True, "r": False, "jo": False, "check": 1}, TypeError),
        ):
            with self.subTest(flags=flags), self.assertRaises(error):
                node.setQuaternion(self._rotation(), **flags)
        self.assertEqual(self._state(node), before)
        self.assertUndoEmpty()

    def test_locked_and_connected_compensation_rejected_before_write(self):
        for fast in (False, True):
            for attribute in ("rotateY", "rotateAxisZ"):
                for connected in (False, True):
                    with self.subTest(fast=fast, attribute=attribute, connected=connected):
                        node = self._node()
                        name = node.getName(full=True)
                        if connected:
                            source = self.make("transform", "source#")
                            cmds.connectAttr(source + ".rx", name + "." + attribute)
                        else:
                            cmds.setAttr(name + "." + attribute, lock=True)
                        before = self._state(node)
                        self.flushUndo()
                        with self.assertRaises(RuntimeError):
                            node.setQuaternion(self._rotation(), r=False, jo=False, preserve=True, fast=fast)
                        self.assertEqual(self._state(node), before)
                        self.assertUndoEmpty()

    def _node(self, kind="transform", order=0):
        parent = self.make("transform", "parent#")
        cmds.setAttr(parent + ".rotate", 15, -25, 37)
        cmds.setAttr(parent + ".scale", 1.2, 1.8, 0.7)
        node = self.make(kind, "target#", parent=parent)
        cmds.setAttr(node + ".rotate", 20, 35, -40)
        cmds.setAttr(node + ".rotateAxis", 10, -15, 5)
        cmds.setAttr(node + ".rotateOrder", order)
        cmds.setAttr(node + ".scale", -1.4, 1.8, 0.8)
        cmds.setAttr(node + ".shear", 0.3, -0.1, 0.15)
        cmds.setAttr(node + ".rotatePivot", 1, 2, 3)
        if kind == "joint":
            cmds.setAttr(node + ".jointOrient", 15, -25, 30)
        cmds.setAttr(node + ".offsetParentMatrix", *list(om2.MEulerRotation(0.1, -0.2, 0.3).asMatrix()), type="matrix")
        return mlib.getNode(node)

    @staticmethod
    def _rotation():
        return om2.MEulerRotation(*(math.radians(value) for value in (-23, 42, 17))).asQuaternion()

    @staticmethod
    def _state(node):
        return [
            cmds.getAttr(node.getName(full=True) + "." + name)
            for name in ("rotateAxis", "rotate", "jointOrient")
            if cmds.attributeQuery(name, node=node.getName(full=True), exists=True)
        ]


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
