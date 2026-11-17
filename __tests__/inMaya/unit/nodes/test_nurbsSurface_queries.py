"""専門ノードの照会・更新をMaya標準APIと照合する。"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class SurfaceQueriesTest(NamespaceCase):
    def test_derivatives_knots_trim_and_ray(self):
        name = cmds.nurbsPlane(name=self.name("surface"), axis=(0, 1, 0), constructionHistory=False)[0]
        surface = mlib.Node(name).getShape()
        fn = surface.mfn()
        self.flushUndo()
        self.assertEqual(surface.getKnots(), (list(fn.knotsInU()), list(fn.knotsInV())))
        self.assertFalse(surface.isTrimmed())
        self.assertFalse(surface.isPointInTrimmedRegion(0.5, 0.5))
        for second in (False, True):
            actual = surface.getDerivativesAtParam(0.5, 0.5, secondOrder=second)
            expected = fn.getDerivativesAtParam(0.5, 0.5, secondOrder=second)
            self.assertEqual(len(actual), 6 if second else 3)
            for value, reference in zip(actual, expected):
                self.assertSequenceAlmostEqual(value, list(reference)[:3])
        result = surface.getRayIntersection((0, 5, 0), (0, -1, 0))
        self.assertIsNotNone(result)
        self.assertSequenceAlmostEqual(result[0], (0, 0, 0), places=6)
        self.assertIsNone(surface.getRayIntersection((10, 5, 0), (0, -1, 0)))
        self.assertUndoEmpty()
        with self.assertRaises(ValueError):
            surface.getRayIntersection((0, 0, 0), (0, 0, 0))
        with self.assertRaises(ValueError):
            surface.isPointInTrimmedRegion(100, 0)
        with self.assertRaises(TypeError):
            surface.getDerivativesAtParam(0.5, 0.5, secondOrder=1)

    def test_world_space_and_trimmed_regions(self):
        name = cmds.nurbsPlane(name=self.name("trimSurface"), axis=(0, 1, 0), width=10, constructionHistory=False)[0]
        boundary = cmds.curveOnSurface(name, degree=1, positionUV=[(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8), (0.2, 0.2)])
        cmds.trim(name, boundary, constructionHistory=False, replaceOriginal=True, locatorU=0.5, locatorV=0.5, selected=0)
        surface = mlib.Node(name).getShape()
        self.assertAlmostEqual(surface.mfn().area(), 36)
        self.assertTrue(surface.isTrimmed())
        self.assertTrue(surface.mfn().isPointInTrimmedRegion(0.5, 0.5))
        self.assertFalse(surface.mfn().isPointInTrimmedRegion(0.05, 0.05))
        self.assertFalse(surface.isPointInTrimmedRegion(0.5, 0.5))
        self.assertTrue(surface.isPointInTrimmedRegion(0.05, 0.05))
        cmds.setAttr(name + ".translate", 2, 3, 4)
        cmds.setAttr(name + ".scale", 2, 3, 4)
        expected = surface.mfn().getDerivativesAtParam(0.5, 0.5, space=om2.MSpace.kWorld, secondOrder=True)
        for actual, value in zip(surface.getDerivativesAtParam(0.5, 0.5, ws=True, secondOrder=True), expected):
            self.assertSequenceAlmostEqual(actual, list(value)[:3])
        hit = surface.getRayIntersection((2, 10, 4), (0, -2, 0), ws=True)
        self.assertIsNotNone(hit)
        self.assertSequenceAlmostEqual(hit[0], (2, 3, 4))
        self.assertIsNone(surface.getRayIntersection((-7, 10, -14), (0, -1, 0), ws=True))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
