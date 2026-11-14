"""``mlib.nodes.mesh`` のテスト。

- 形状ラッパーと標準コンストレイントを Maya 内で検証する。
"""

import importlib
import sys
import unittest
import uuid

import maya.cmds as cmds

import mlib

mlib.reload()


mlib_cmds = importlib.import_module("mlib.cmds")


class ShapesConstraintsTest(unittest.TestCase):
    """専用名前空間に作成したノードだけで動作を確認する。"""

    def setUp(self):
        self.selection = cmds.ls(selection=True, long=True) or []
        self.previous_namespace = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)
        self.namespace = ":mlibShapesConstraints_" + uuid.uuid4().hex
        cmds.namespace(add=self.namespace)
        cmds.namespace(set=self.namespace)

    def tearDown(self):
        cmds.namespace(set=self.previous_namespace)
        cmds.namespace(removeNamespace=self.namespace, deleteNamespaceContent=True)
        if self.selection:
            cmds.select(self.selection, replace=True)
        else:
            cmds.select(clear=True)

    def getTransform(self):
        return mlib_cmds.createNode("transform")

    def test_mesh_and_curve_geometry(self):
        cube = mlib.Node(cmds.polyCube(constructionHistory=False)[0])
        mesh = cube.getShape()
        self.assertIsInstance(mesh, mlib.Mesh)
        self.assertEqual((mesh.getNumVertices(), mesh.getNumEdges(), mesh.getNumPolygons()), (8, 12, 6))
        local_x = mesh.getPoints()[0].x
        cmds.setAttr(cube.getFullName() + ".translateX", 5)
        self.assertAlmostEqual(mesh.getPoints(worldSpace=True)[0].x, local_x + 5)

        curve = mlib.Node(cmds.curve(degree=1, point=[(0, 0, 0), (3, 0, 0), (3, 4, 0)]))
        shape = curve.getShape()
        self.assertIsInstance(shape, mlib.NurbsCurve)
        self.assertEqual((shape.getNumCVs(), shape.getNumSpans(), shape.getDegree()), (3, 2, 1))
        self.assertAlmostEqual(shape.getLength(), 7)
        cmds.setAttr(curve.getFullName() + ".scaleX", 2)
        self.assertAlmostEqual(shape.getLength(), 7)
        cmds.setAttr(curve.getFullName() + ".translateY", 2)
        self.assertAlmostEqual(shape.getCvPositions(worldSpace=True)[0].y, 2)
        self.assertAlmostEqual(shape.getCvPositions()[0].y, 0)
        with self.assertRaises(ValueError):
            shape.getLength(0)

    def test_mesh_normals_object_and_world_space(self):
        cube = mlib.Node(cmds.polyCube(constructionHistory=False)[0])
        mesh = cube.getShape()

        local_normals = mesh.getVertexNormals()
        self.assertEqual(len(local_normals), mesh.getNumVertices())
        for normal in local_normals:
            self.assertAlmostEqual(sum(c * c for c in (normal.x, normal.y, normal.z)) ** 0.5, 1.0, places=5)

        cmds.setAttr(cube.getFullName() + ".rotateY", 90)
        world_normals = mesh.getVertexNormals(worldSpace=True)
        self.assertEqual(len(world_normals), mesh.getNumVertices())
        self.assertFalse(all(abs(a.x - b.x) < 1e-5 and abs(a.y - b.y) < 1e-5 and abs(a.z - b.z) < 1e-5 for a, b in zip(local_normals, world_normals)))

        weighted = mesh.getVertexNormals(angleWeighted=True)
        self.assertEqual(len(weighted), mesh.getNumVertices())

    def mirror_shapes(self):
        """非対称カーブと履歴付きメッシュを変換済みの親の下へ作成する。"""
        cube = mlib.Node(cmds.polyCube()[0])
        curve = mlib.Node(cmds.curve(degree=1, point=[(1, 2, 3), (4, 1, -2), (2, 5, 1)]))
        parent = self.getTransform()
        cmds.setAttr(parent.getFullName() + ".translate", 4, -2, 3)
        cmds.setAttr(parent.getFullName() + ".rotate", 23, 41, -17)
        cmds.setAttr(parent.getFullName() + ".scale", 2, 0.7, 1.3)
        cmds.parent(cube.getFullName(), curve.getFullName(), parent.getFullName(), relative=True)
        return [cube.getShape(), curve.getShape()]

    def positions(self, shape, ws=False):
        """API の内部距離単位で形状の全位置を返す。"""
        points = shape.getPoints(ws) if isinstance(shape, mlib.Mesh) else shape.getCvPositions(ws)
        return [tuple(point)[:3] for point in points]

    def assert_positions(self, actual, expected):
        """全成分を許容誤差付きで比較する。"""
        self.assertEqual(len(actual), len(expected))
        for point, reference in zip(actual, expected):
            for component, value in zip(point, reference):
                # Mesh の座標保存精度を考慮し、距離単位変更時も相対誤差で比較する。
                self.assertAlmostEqual(component, value, delta=max(1e-5, abs(value) * 1e-6))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
