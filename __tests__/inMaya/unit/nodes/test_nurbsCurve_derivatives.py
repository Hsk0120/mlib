"""専門ノードの照会・更新をMaya標準APIと照合する。"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class CurveDerivativesTest(NamespaceCase):
    def test_derivatives_and_space(self):
        name = cmds.curve(name=self.name("curve"), degree=3, point=[(0, 0, 0), (1, 3, 0), (3, 2, 0), (4, 0, 1)])
        cmds.setAttr(name + ".scale", 2, 3, 4)
        curve = mlib.Node(name).getShape()
        self.flushUndo()
        for world in (False, True):
            with self.subTest(world=world):
                values = curve.getDerivativesAtParam(0.4, world, secondOrder=True)
                direct = curve.mfn().getDerivativesAtParam(0.4, space=om2.MSpace.kWorld if world else om2.MSpace.kObject, dUU=True)
                self.assertEqual(len(values), 3)
                for actual, expected in zip(values, direct):
                    self.assertSequenceAlmostEqual(actual, list(expected)[:3])
                self.assertEqual(len(curve.getDerivativesAtParam(0.4)), 2)
        self.assertUndoEmpty()
        with self.assertRaises(ValueError):
            curve.getDerivativesAtParam(-10)
        with self.assertRaises(TypeError):
            curve.getDerivativesAtParam(0.4, False, ws=False)
        with self.assertRaises(TypeError):
            curve.getDerivativesAtParam(0.4, secondOrder=1)

    def test_degenerate_derivative_is_zero(self):
        name = cmds.curve(name=self.name("zero"), degree=1, point=[(1, 1, 1), (1, 1, 1)])
        curve = mlib.Node(name).getShape()
        self.assertAlmostEqual(curve.getDerivativesAtParam(0.5)[1].length(), 0)

    def test_periodic_endpoint_derivatives(self):
        name = cmds.circle(name=self.name("periodic"), constructionHistory=False)[0]
        curve = mlib.Node(name).getShape()
        start, end = curve.getParamRange()
        first = curve.getDerivativesAtParam(start, secondOrder=True)
        last = curve.getDerivativesAtParam(end, secondOrder=True)
        for a, b in zip(first, last):
            self.assertSequenceAlmostEqual(a, b)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
