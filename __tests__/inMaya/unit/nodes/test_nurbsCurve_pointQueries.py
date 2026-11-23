"""カーブ上の判定と最寄り点照会の違いを検証する。"""

import sys
import unittest

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class CurvePointTest(NamespaceCase):
    def setUp(self):
        super().setUp()
        self.transform = mlib.getNode(cmds.curve(name=self.ns + ":curve", degree=1, point=[(0, 0, 0), (2, 0, 0), (2, 2, 0)]))
        self.shape = self.transform.getShape()

    def test_point_on_curve_and_off_curve(self):
        self.assertTrue(self.shape.isPointOnCurve((1, 0, 0)))
        self.assertAlmostEqual(self.shape.getParam(point=(1, 0, 0)), 0.5)
        self.assertFalse(self.shape.isPointOnCurve((1, 1, 0)))
        with self.assertRaises(RuntimeError):
            self.shape.getParam(point=(1, 1, 0))
        self.assertAlmostEqual(self.shape.getParam(point=(2, 2, 0)), 2.0)
        self.assertTrue(self.shape.isPointOnCurve((1, 0.001, 0), tolerance=0.01))

    def test_world_space_and_read_only(self):
        cmds.setAttr(self.transform.getName() + ".translateX", 10)
        cmds.setAttr(self.transform.getName() + ".scaleX", 3)
        before = cmds.ls(long=True)
        undo_name = cmds.undoInfo(query=True, undoName=True)
        self.assertAlmostEqual(self.shape.getParam(point=(13, 0, 0), ws=True), 0.5)
        self.assertTrue(self.shape.isPointOnCurve((13, 0, 0), worldSpace=True))
        self.assertFalse(self.shape.isPointOnCurve((13, 0, 0)))
        self.assertEqual(cmds.ls(long=True), before)
        self.assertEqual(cmds.undoInfo(query=True, undoName=True), undo_name)

    def test_invalid_inputs(self):
        for method in (lambda point, **kwargs: self.shape.getParam(point=point, **kwargs), self.shape.isPointOnCurve):
            with self.assertRaises(TypeError):
                method((1, 0, 0), worldSpace=False, ws=False)
            with self.assertRaises(ValueError):
                method((1, 0, 0), tolerance=-1)
            with self.assertRaises(ValueError):
                method((float("nan"), 0, 0))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
