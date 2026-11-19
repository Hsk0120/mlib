"""Maya標準の照会と、既存の取得対象との違いを検証する。"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class SurfaceStructureTest(NamespaceCase):
    def test_plane_and_sphere_match_native(self):
        for command in (cmds.nurbsPlane, cmds.sphere):
            node = command(name=self.ns + ":surface", constructionHistory=False)[0]
            shape = mlib.getNode(node).getShape()
            fn = om2.MFnNurbsSurface(shape.mpath())
            self.assertEqual(shape.getNumPatches(), (fn.numPatchesInU, fn.numPatchesInV))
            self.assertEqual(shape.getNumPatches()[0] * shape.getNumPatches()[1], fn.numPatches)
            self.assertEqual(shape.isBezier(), fn.isBezier)
            self.assertEqual(shape.isUniform(), fn.isUniform)
            self.assertEqual(shape.isFoldedOnBispan(), fn.isFoldedOnBispan)

    def test_zero_width_spans_are_excluded(self):
        node = cmds.nurbsPlane(name=self.ns + ":patches", constructionHistory=False, patchesU=2, patchesV=3)[0]
        shape = mlib.getNode(node).getShape()
        cmds.insertKnotSurface(shape.getFullName(), parameter=0.5, direction=0, numberOfKnots=2, addKnots=True, constructionHistory=False, replaceOriginal=True)
        self.assertEqual(shape.getNumSpans(), (2, 5))
        self.assertEqual(shape.getNumPatches(), (2, 4))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
