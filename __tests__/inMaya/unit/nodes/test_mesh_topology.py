"""``Mesh.getTopology`` と ``Mesh.copyUVSet(replace=True)`` のテスト。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class MeshTopologyTest(NamespaceCase):
    """getTopology は MFnMesh.getVertices と同じ値を list で返す。"""

    PREFIX = "mlibMeshTopology_"

    def test_matches_om2(self):
        """三角形・四角形の混ざったメッシュで om2 と一致する。"""
        transform = cmds.polyCylinder(name=self.name("cylinder"), subdivisionsX=5, constructionHistory=False)[0]
        mesh = mlib.getNode(transform).getShape()
        counts, vertices = mesh.getTopology()
        expected = mesh.mfn().getVertices()
        self.assertEqual(counts, list(expected[0]))
        self.assertEqual(vertices, list(expected[1]))
        self.assertIsInstance(counts, list)
        self.assertEqual(sum(counts), len(vertices))


class CopyUVSetReplaceTest(NamespaceCase):
    """copyUVSet(replace=True) は既にあるUVセットのUVを置き換える。"""

    PREFIX = "mlibCopyUVSetReplace_"

    def mesh(self):
        """map1を動かしたコピー(moved)を持つメッシュを返す。"""
        transform = cmds.polyPlane(name=self.name("plane"), subdivisionsX=2, subdivisionsY=2, constructionHistory=False)[0]
        mesh = mlib.getNode(transform).getShape()
        mesh.copyUVSet("map1", "moved")
        cmds.polyEditUV(transform + ".map[*]", uValue=0.5, vValue=0.25, uvSetName="moved")
        return mesh

    def uvs(self, mesh, uv_set):
        """フェースの頂点ごとのUVを返す(UVの番号の並びには左右されない)。"""
        fn = mesh.mfn()
        return [
            tuple(round(value, 6) for value in fn.getPolygonUV(face, corner, uv_set))
            for face in range(fn.numPolygons)
            for corner in range(fn.polygonVertexCount(face))
        ]

    def test_replace_existing(self):
        """targetがあれば値を置き換え、無ければ新しく作る。現在のUVセットとUndo 1回を確かめる。"""
        mesh = self.mesh()
        self.assertNotEqual(self.uvs(mesh, "map1"), self.uvs(mesh, "moved"))
        self.flushUndo()
        mesh.copyUVSet("moved", "map1", replace=True)
        expected = self.uvs(mesh, "moved")
        self.assertUndoesInOneStep(lambda: self.assertNotEqual(self.uvs(mesh, "map1"), expected), lambda: self.assertEqual(self.uvs(mesh, "map1"), expected))
        self.assertEqual(mesh.getCurrentUVSet(), "map1")
        mesh.copyUVSet("moved", "fresh", replace=True)
        self.assertIn("fresh", mesh.getUVSetNames())
        self.assertFalse(mesh.getHistory(type="polyCopyUV"))

    def test_errors(self):
        """replaceを指定しなければ従来どおり拒否し、型と同じ名前を確かめる。"""
        mesh = self.mesh()
        with self.assertRaises(ValueError):
            mesh.copyUVSet("map1", "moved")
        with self.assertRaises(ValueError):
            mesh.copyUVSet("map1", "map1", replace=True)
        with self.assertRaises(TypeError):
            mesh.copyUVSet("map1", "moved", replace=1)
        with self.assertRaises(ValueError):
            mesh.copyUVSet("missing", "moved", replace=True)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
