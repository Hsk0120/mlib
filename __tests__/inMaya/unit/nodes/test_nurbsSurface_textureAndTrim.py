"""NURBSの明示UVとトリム境界構成を確認する。"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class SurfaceTextureAndTrimTest(NamespaceCase):
    """構成番号と値をOpenMayaに照合する。"""

    def surface(self, sphere=False, patches=1):
        if sphere:
            name = cmds.sphere(name=self.name("sphere#"), constructionHistory=False)[0]
        else:
            name = cmds.nurbsPlane(name=self.name("surface#"), patchesU=patches, patchesV=patches, constructionHistory=False)[0]
        return mlib.getNode(name).getShape()

    def trim_hole(self, surface):
        name = surface.getName(full=True)
        boundary = cmds.curveOnSurface(name, degree=1, positionUV=[(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8), (0.2, 0.2)])
        cmds.trim(name, boundary, constructionHistory=False, replaceOriginal=True, locatorU=0.05, locatorV=0.05, selected=0)

    def test_trim_boundary_outer_inner_and_untrimmed(self):
        for sphere in (False, True):
            surface = self.surface(sphere)
            self.assertEqual(surface.getTrimBoundaryInfo(), [[]])
        surface = self.surface()
        self.trim_hole(surface)
        self.flushUndo()
        actual = surface.getTrimBoundaryInfo()
        self.assertEqual(actual, [[(om2.MFnNurbsSurface.kOuter, 4), (om2.MFnNurbsSurface.kInner, 4)]])
        fn = surface.mfn()
        expected = [
            [(fn.boundaryType(region, boundary), fn.numEdges(region, boundary)) for boundary in range(fn.numBoundaries(region))]
            for region in range(fn.numRegions)
        ]
        self.assertEqual(actual, expected)
        self.assertEqual(mlib.Nodes([surface]).getTrimBoundaryInfo(), [actual])
        actual[0].clear()
        self.assertEqual(len(surface.getTrimBoundaryInfo()[0]), 2)
        self.assertUndoEmpty()

    def test_uv_absent_default_and_invalid_shape(self):
        for sphere in (False, True):
            surface = self.surface(sphere)
            self.flushUndo()
            with self.assertRaisesRegex(RuntimeError, "明示的なテクスチャUV"):
                surface.getUVData()
            self.assertUndoEmpty()
        empty = mlib.createNode("nurbsSurface", name=self.name("empty"))
        for operation in (empty.getUVData, empty.getTrimBoundaryInfo):
            with self.assertRaises(RuntimeError):
                operation()

    def test_explicit_uv_partial_assignments_periodic_and_trim(self):
        for kind in ("plane", "sphere", "trim"):
            with self.subTest(kind=kind):
                surface = self.surface(sphere=kind == "sphere", patches=2)
                if kind == "trim":
                    self.trim_hole(surface)
                fn = surface.mfn()
                fn.setUVs([0.1, 0.9, 0.8, 0.2, 0.4], [0.2, 0.1, 0.9, 0.8, 0.6])
                counts = [4] + [0] * (fn.numPatches - 1)
                fn.assignUVs(counts, [3, 1, 0, 2])
                self.flushUndo()
                actual = surface.getUVData()
                self.assertEqual(actual, (list(zip(*fn.getUVs())), counts, [3, 1, 0, 2]))
                self.assertEqual(mlib.Nodes([surface]).getUVData(), [actual])
                self.assertEqual(len(actual[0]), 5)
                self.assertEqual(tuple(list(a) for a in fn.getAssignedUVs()), actual[1:])
                actual[0][0] = (99, 99)
                actual[1][0] = 0
                actual[2][0] = -1
                self.assertNotEqual(surface.getUVData()[0][0], (99, 99))
                self.assertEqual(surface.getUVData()[1][0], 4)
                self.assertEqual(surface.getUVData()[2][0], 3)
                self.assertUndoEmpty()

    def test_set_uv_data_matches_openmaya_and_rejects_invalid(self):
        """setUVData(fast=True)の結果がom2のUVと一致してUndoに載らず、型・長さ・数の誤りは何も変えずに例外。"""
        surface = self.surface(patches=2)
        uvs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        counts = [4, 0, 4, 0]
        indices = [0, 1, 2, 3, 3, 2, 1, 0]
        self.flushUndo()
        self.assertIsNone(surface.setUVData(uvs, counts, indices, fast=True))
        self.assertUndoEmpty()
        fn = surface.mfn()
        self.assertEqual(list(zip(*fn.getUVs())), uvs)
        self.assertEqual(tuple(list(a) for a in fn.getAssignedUVs()), (counts, indices))
        before = surface.getUVData()
        for label, args, kwargs, error in (
            ("not fast", (uvs, counts, indices), {}, NotImplementedError),
            ("fast type", (uvs, counts, indices), {"fast": 1}, TypeError),
            ("empty uvs", ([], counts, indices), {"fast": True}, ValueError),
            ("uv length", ([(0.0, 0.0, 0.0)] * 4, counts, indices), {"fast": True}, ValueError),
            ("count float", (uvs, [4.0, 0, 4, 0], indices), {"fast": True}, TypeError),
            ("index float", (uvs, counts, [0.0, *indices[1:]]), {"fast": True}, TypeError),
            ("count three", (uvs, [3, 0, 4, 0], indices[:-1]), {"fast": True}, ValueError),
            ("count length", (uvs, [4, 0], indices[:4]), {"fast": True}, ValueError),
            ("index range", (uvs, counts, [9, *indices[1:]]), {"fast": True}, ValueError),
            ("index length", (uvs, counts, indices[:-1]), {"fast": True}, ValueError),
        ):
            with self.subTest(label=label):
                with self.assertRaises(error):
                    surface.setUVData(*args, **kwargs)
                self.assertEqual(surface.getUVData(), before)
        self.assertUndoEmpty()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
