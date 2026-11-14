"""``mlib.components.vertex`` のテスト。

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

    def test_component_collections_and_live_positions(self):
        for shape in self.mirror_shapes():
            is_mesh = isinstance(shape, mlib.Mesh)
            component_type = mlib.Vertex if is_mesh else mlib.CV
            collection_type = mlib.Vertices if is_mesh else mlib.CVs
            collection = shape.getVertices([2, 0, 2]) if is_mesh else shape.getCVs([2, 0, 2])
            self.assertIsInstance(collection, collection_type)
            self.assertEqual(collection.indices, (2, 0))
            self.assertEqual(len(collection), 2)
            self.assertEqual([item.index for item in collection], [2, 0])
            self.assertIsInstance(collection[0], component_type)
            self.assertEqual(collection[-1].index, 0)
            self.assertIsInstance(collection[:1], collection_type)
            self.assertEqual(collection[:1].indices, (2,))
            self.assertEqual(collection[0].getPosition(), collection.getPosition()[0])
            single = shape.getVertex(2) if is_mesh else shape.getCV(2)
            cmds.xform(single.getFullName(), objectSpace=True, translation=(0.25, 0.5, -0.75))
            self.assert_positions([single.getPosition()], [(0.25, 0.5, -0.75)])
            old_name = single.getFullName()
            shape.rename("renamedMirrorShape")
            self.assertNotEqual(single.getFullName(), old_name)
            self.assertTrue(cmds.objExists(single.getFullName()))
            other_type = mlib.CVs if is_mesh else mlib.Vertices
            with self.assertRaises(TypeError):
                other_type(shape, [])
            cmds.delete(shape.getFullName())
            with self.assertRaises(RuntimeError):
                single.getPosition()

    def test_xyz_and_mesh_components(self):
        mesh, curve = self.mirror_shapes()
        for item in (mesh.getVertex(0), curve.getCV(0)):
            position = item.getPosition()
            for index, axis in enumerate("xyz"):
                self.assertAlmostEqual(getattr(item, "getPosition" + axis.upper())(), position[index])
            cmds.xform(item.getFullName(), worldSpace=True, translation=(3, 4, 5))
            self.assert_positions([item.getPosition(worldSpace=True)], [(3, 4, 5)])
        self.assertEqual(len(mesh.getEdges()), mesh.getNumEdges())
        self.assertEqual(len(mesh.getFaces()), mesh.getNumPolygons())
        self.assertEqual(len(mesh.getEdge(0).getVertices()), 2)
        self.assertEqual(len(mesh.getFace(0).getVertices()), 4)
        self.assertEqual(len(mesh.getEdges().getVertices()), mesh.getNumVertices())
        self.assertEqual(len(mesh.getFaces().getVertices()), mesh.getNumVertices())
        self.assertEqual(len(mesh.getUVs()), mesh.getNumUVs())
        uv = mesh.getUV(0)
        self.assertEqual(uv.getPosition(), (uv.getU(), uv.getV()))
        self.assertEqual(mesh.getUVs([0]).getPosition(), [uv.getPosition()])
        for collection in (mlib.Edges, mlib.Faces, mlib.UVs):
            with self.assertRaises(TypeError):
                collection(curve)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
