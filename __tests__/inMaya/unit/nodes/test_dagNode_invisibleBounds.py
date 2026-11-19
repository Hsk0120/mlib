"""非表示形状を含むボックスの座標空間と単位を検証する。"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class InvisibleBoundsTest(NamespaceCase):
    def test_hidden_children_units_and_space(self):
        root = cmds.createNode("transform", name=self.name("root"))
        cube = cmds.polyCube(name=self.name("cube"))[0]
        cmds.parent(cube, root)
        cmds.setAttr(cube + ".tx", 3)
        cmds.setAttr(cube + ".visibility", False)
        cmds.setAttr(root + ".ry", 20)
        for unit in ("cm", "m"):
            cmds.currentUnit(linear=unit)
            for node in [mlib.getNode(root), mlib.getNode(cube)]:
                for world in (False, True):
                    with self.subTest(unit=unit, node=node.getFullName(), world=world):
                        box = node.getBoundingBox(ws=world, includeInvisible=True)
                        expected = cmds.xform(node.getFullName(), q=True, boundingBoxInvisible=True, worldSpace=world)
                        expected = [om2.MDistance(v, om2.MDistance.uiUnit()).asCentimeters() for v in expected]
                        actual = list(box.min)[:3] + list(box.max)[:3]
                        for a, b in zip(actual, expected):
                            self.assertAlmostEqual(a, b)
                        self.assertGreater(box.width, 0)

    def test_shape_keeps_own_geometry(self):
        shape = mlib.getNode(cmds.polyCube(name=self.name("cube"))[0]).getShape()
        shape.hide()
        for world in (False, True):
            regular = shape.getBoundingBox(ws=world)
            included = shape.getBoundingBox(ws=world, includeInvisible=True)
            self.assertEqual(tuple(regular.min), tuple(included.min))
            self.assertEqual(tuple(regular.max), tuple(included.max))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
