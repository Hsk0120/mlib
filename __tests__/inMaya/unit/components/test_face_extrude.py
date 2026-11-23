"""``Faces.extrude`` のテスト。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class ExtrudeTest(NamespaceCase):
    """polyExtrudeFacetと同じ結果になり、作ったpolyExtrudeFaceを返す。"""

    PREFIX = "mlibFaceExtrude_"

    def setUp(self):
        super().setUp()
        self.cube = cmds.polyCube(name=f"{self.ns}:cube", constructionHistory=False)[0]
        self.curve = cmds.curve(name=f"{self.ns}:path", point=[(0, 0.5, 0), (0, 2, 0), (1, 4, 0), (2, 5, 0)], degree=3)
        cmds.flushUndo()

    def faces(self):
        return cmds.polyEvaluate(self.cube, face=True)

    def test_matches_cmds(self):
        other = cmds.polyCube(name=f"{self.ns}:other", constructionHistory=False)[0]
        node = mlib.ls(f"{self.cube}.f[1]").extrude(curve=self.curve, divisions=3)
        cmds.polyExtrudeFacet(f"{other}.f[1]", inputCurve=self.curve, divisions=3, keepFacesTogether=True, constructionHistory=True)
        self.assertIsInstance(node, mlib.Node)
        self.assertEqual(node.getType(), "polyExtrudeFace")
        self.assertEqual(self.faces(), cmds.polyEvaluate(other, face=True))
        self.assertEqual(cmds.getAttr(f"{node}.divisions"), 3)
        self.assertEqual(cmds.listConnections(f"{node}.inputProfile", shapes=True), cmds.listRelatives(self.curve, shapes=True))
        points = cmds.xform(f"{self.cube}.vtx[*]", query=True, translation=True, worldSpace=True)
        expected = cmds.xform(f"{other}.vtx[*]", query=True, translation=True, worldSpace=True)
        for value, wanted in zip(points, expected):
            self.assertAlmostEqual(value, wanted, places=5)

    def test_curve_shape_and_without_curve(self):
        shape = mlib.getNode(self.curve).getShape()
        mlib.ls(f"{self.cube}.f[1]").extrude(curve=shape)
        self.assertEqual(self.faces(), 10)
        mlib.ls(f"{self.cube}.f[0]").extrude()
        self.assertEqual(self.faces(), 14)

    def test_keep_faces_together(self):
        mlib.ls(f"{self.cube}.f[0:1]").extrude(keepFacesTogether=False)
        self.assertEqual(self.faces(), 14)

    def test_one_undo(self):
        mlib.ls(f"{self.cube}.f[1]").extrude(curve=self.curve, divisions=2)
        cmds.undo()
        self.assertEqual(self.faces(), 6)
        self.assertFalse(cmds.ls(f"{self.ns}:*", type="polyExtrudeFace"))

    def test_invalid(self):
        faces = mlib.ls(f"{self.cube}.f[1]")
        for kwargs, error in (
            ({"divisions": 0}, ValueError),
            ({"divisions": 1.0}, TypeError),
            ({"divisions": True}, TypeError),
            ({"keepFacesTogether": 1}, TypeError),
            ({"curve": self.cube}, TypeError),
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(error):
                faces.extrude(**kwargs)
        self.assertEqual(self.faces(), 6)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
