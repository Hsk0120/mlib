"""``mlib.nodes.nurbsSurface`` の NurbsSurface の、不正な入力・ロック・無効なシェイプでの例外を確かめる。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class NurbsSurfaceErrorTest(NamespaceCase):
    """docstringの Raises に書いた例外が出る。"""

    PREFIX = "mlibSpecNurbsSurfaceEdge_"

    def setUp(self):
        super().setUp()
        transform = cmds.nurbsPlane(constructionHistory=False, name=self.name("plane"))[0]
        self.surface = mlib.getNode(transform).getShape()
        self.shape = self.surface.getName(full=True)

    def empty(self):
        return mlib.createNode("nurbsSurface", name=self.name("emptyShape"))

    def test_shape_without_geometry(self):
        """形状データの無いシェイプの getKnots・getClosestPoint は RuntimeError。"""
        empty = self.empty()
        with self.assertRaises(RuntimeError):
            empty.getKnots()
        with self.assertRaises(RuntimeError):
            empty.getClosestPoint((0, 0, 0))

    def test_closest_point_rejects_non_finite(self):
        """getClosestPoint の点に有限でない成分があれば ValueError。"""
        with self.assertRaises(ValueError):
            self.surface.getClosestPoint((float("nan"), 0, 0))

    def test_type_errors(self):
        """isPointInTrimmedRegion・getRayIntersection・isPointOnSurface は、引数の型が違えば TypeError。"""
        with self.assertRaises(TypeError):
            self.surface.isPointInTrimmedRegion("a", 0.5)
        with self.assertRaises(TypeError):
            self.surface.getRayIntersection("abc", (0, 1, 0))
        with self.assertRaises(TypeError):
            self.surface.isPointOnSurface("abc")
        with self.assertRaises(TypeError):
            self.surface.isPointOnSurface((0, 0, 0), tolerance="x")
        self.assertTrue(self.surface.isPointOnSurface((0, 0, 0)))

    def test_set_uv_data_on_locked_surface(self):
        """ロックした曲面への setUVData(fast=True) は RuntimeError で、明示UVは作られない。"""
        cmds.lockNode(self.shape, lock=True)
        try:
            with self.assertRaises(RuntimeError):
                self.surface.setUVData([(0, 0), (1, 0), (1, 1), (0, 1)], [4], [0, 1, 2, 3], fast=True)
        finally:
            cmds.lockNode(self.shape, lock=False)
        with self.assertRaises(RuntimeError):
            self.surface.getUVData()

    def test_mfn_of_deleted_surface(self):
        """削除した曲面の mfn は RuntimeError。複数形から呼んでも同じ。"""
        nodes = mlib.ls(self.shape)
        cmds.delete(cmds.listRelatives(self.shape, parent=True, fullPath=True))
        with self.assertRaises(RuntimeError):
            self.surface.mfn()
        with self.assertRaises(RuntimeError):
            nodes.mfn()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
