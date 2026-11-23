"""トリム境界のカーブをシーン編集なしで値として取得する。"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class SurfaceTrimCurveDataTest(NamespaceCase):
    def test_curve_values_and_no_nodes_created(self):
        name = cmds.nurbsPlane(name=self.ns + ":surface", constructionHistory=False)[0]
        shape = mlib.getNode(name).getShape()
        boundary = cmds.curveOnSurface(shape.getFullName(), degree=1, positionUV=[(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8), (0.2, 0.2)])
        cmds.trim(shape.getFullName(), boundary, constructionHistory=False, replaceOriginal=True, locatorU=0.05, locatorV=0.05, selected=0)
        fn = shape.mfn()
        before = cmds.ls(long=True)
        undo_name = cmds.undoInfo(query=True, undoName=True)
        for parametric in (False, True):
            data = shape.getTrimBoundaryCurveData(0, 1, 0, parametric=parametric)
            curves = fn.edge(0, 1, 0, parametric)
            self.assertEqual(len(data), len(curves))
            self.assertTrue(data)
            for item, curve in zip(data, curves):
                native = om2.MFnNurbsCurve(curve)
                self.assertEqual(item["degree"], native.degree)
                self.assertEqual(item["form"], native.form)
                self.assertEqual(item["knots"], list(native.knots()))
                self.assertEqual(item["cvs"], [(p.x, p.y, p.z, p.w) for p in native.cvPositions()])
            data[0]["cvs"].clear()
            self.assertTrue(shape.getTrimBoundaryCurveData(0, 1, 0, parametric=parametric)[0]["cvs"])
        self.assertEqual(cmds.ls(long=True), before)
        self.assertEqual(cmds.undoInfo(query=True, undoName=True), undo_name)
        for args in ((-1, 0, 0), (0, 99, 0), (0, 0, 99)):
            with self.assertRaises(IndexError):
                shape.getTrimBoundaryCurveData(*args)
        with self.assertRaises(TypeError):
            shape.getTrimBoundaryCurveData(True, 0, 0)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
