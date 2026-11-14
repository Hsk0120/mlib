"""``Transform.getTransformation``・``setTransformation`` のテスト。

ピボット・回転順序・rotateAxis・jointOrient を含めた値の取得と設定、cmds の値との一致、Undo 1回、
fast が Undo に残らないこと、不正な入力の例外を確かめる。
"""

import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.maths import Matrix, Transformation
from mlib.nodes import Node

ATTRS = ("t", "r", "s", "sh", "ra", "rp", "rpt", "sp", "spt")
VALUES = {
    "t": (1, 2, 3),
    "r": (10, 20, 30),
    "s": (1.5, 2, 0.5),
    "sh": (0.1, 0.2, 0.3),
    "ra": (5, 6, 7),
    "rp": (0.5, 1, -1),
    "rpt": (0.1, 0.2, 0.3),
    "sp": (1, 0, 2),
    "spt": (0.3, 0.1, 0.2),
}


class TransformationTest(NamespaceCase):
    PREFIX = "mlibTransformTransformation_"

    def source(self, kind="transform"):
        cmds.select(clear=True)
        name = self.make(kind, "source#")
        cmds.setAttr(name + ".rotateOrder", 4)
        for attr in ATTRS:
            cmds.setAttr(f"{name}.{attr}", *VALUES[attr])
        if kind == "joint":
            cmds.setAttr(name + ".jo", 15, 25, 35)
        return name

    def state(self, name, kind="transform"):
        attrs = ATTRS + (("jo",) if kind == "joint" else ())
        return [cmds.getAttr(name + ".rotateOrder")] + [value for attr in attrs for value in cmds.getAttr(f"{name}.{attr}")[0]]

    def test_get_matches_maya_matrix(self):
        for kind in ("transform", "joint"):
            with self.subTest(kind=kind):
                name = self.source(kind)
                value = Node(name).getTransformation()
                self.assertIsInstance(value, Transformation)
                self.assertEqual(value.rotateOrder, 4)
                self.assertSequenceAlmostEqual(tuple(value.translate), VALUES["t"])
                self.assertSequenceAlmostEqual(tuple(value.rotatePivot), VALUES["rp"])
                self.assertSequenceAlmostEqual(list(value.matrix), cmds.getAttr(name + ".matrix"))

    def test_joint_under_scaled_parent_includes_inverse_scale(self):
        cmds.select(clear=True)
        root = cmds.joint(name=self.name("root"))
        cmds.setAttr(root + ".s", 2, 3, 4)
        child = cmds.joint(name=self.name("child"), position=(1, 2, 3))
        value = Node(child).getTransformation()
        self.assertSequenceAlmostEqual(tuple(value.inverseScale), (2, 3, 4))
        self.assertSequenceAlmostEqual(list(value.matrix), cmds.getAttr(child + ".matrix"))

    def test_set_copies_all_values_with_one_undo(self):
        for kind in ("transform", "joint"):
            for fast in (False, True):
                with self.subTest(kind=kind, fast=fast):
                    source = self.source(kind)
                    cmds.select(clear=True)
                    target = self.make(kind, "target#")
                    before = self.state(target, kind)
                    node = Node(target)
                    self.flushUndo()
                    self.assertIs(node.setTransformation(Node(source).getTransformation(), fast=fast), node)
                    self.assertSequenceAlmostEqual(self.state(target, kind), self.state(source, kind), places=6)
                    self.assertSequenceAlmostEqual(cmds.getAttr(target + ".matrix"), cmds.getAttr(source + ".matrix"), places=6)
                    if fast:
                        self.assertUndoEmpty()
                    else:
                        after = self.state(target, kind)
                        self.assertUndoesInOneStep(
                            lambda: self.assertSequenceAlmostEqual(self.state(target, kind), before, places=6),
                            lambda: self.assertSequenceAlmostEqual(self.state(target, kind), after, places=6),
                        )

    def test_same_value_writes_nothing(self):
        name = self.source()
        node = Node(name)
        self.flushUndo()
        node.setTransformation(node.getTransformation())
        self.assertUndoEmpty()

    def test_invalid_inputs(self):
        node = Node(self.make())
        with self.assertRaises(TypeError):
            node.setTransformation(Matrix())
        with self.assertRaises(TypeError):
            node.setTransformation(Transformation(), fast=1)
        cmds.setAttr(str(node) + ".tx", lock=True)
        with self.assertRaises(RuntimeError):
            node.setTransformation(Transformation(translate=(1, 0, 0)))


if __name__ == "__main__":
    unittest.main()
