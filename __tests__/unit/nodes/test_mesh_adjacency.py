"""``mlib.nodes.mesh`` のテスト。

- Shape 系(Mesh・NurbsCurve・Camera)とデフォーマー(Cluster)の照会の約束を固定する(担当C)。
"""

import math
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.nodes import Camera, Cluster, Mesh, Node, NurbsCurve
from support.namespaceCase import NamespaceCase


class _SpecCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、共通基底からの差分。"""

    PREFIX = "mlibSpecNodeGeo_"
    ENABLE_UNDO = False


class VertexAdjacencyTest(_SpecCase):
    """getVertexAdjacency は頂点ごとの (隣接頂点, cm の距離) をエッジ順に返す。"""

    def setUp(self):
        super().setUp()
        self.plane = cmds.polyPlane(name=self.name("plane"), subdivisionsX=1, subdivisionsY=1,
                                    width=2, height=2, constructionHistory=False)[0]
        cmds.setAttr(self.plane + ".scale", 3, 3, 3)
        self.mesh = Node(self.plane).getShape()

    def expected(self, world):
        """MFnMesh のエッジと頂点座標から独立に求める。"""
        space = om2.MSpace.kWorld if world else om2.MSpace.kObject
        fn = om2.MFnMesh(om2.MSelectionList().add(self.plane).getDagPath(0))
        points = fn.getPoints(space)
        result = [[] for _ in points]
        for edge in range(fn.numEdges):
            first, second = fn.getEdgeVertices(edge)
            length = points[first].distanceTo(points[second])
            result[first].append((second, length))
            result[second].append((first, length))
        return result

    def assertAdjacency(self, actual, expected):
        self.assertEqual(len(actual), len(expected))
        for actual_row, expected_row in zip(actual, expected):
            self.assertEqual([index for index, _ in actual_row], [index for index, _ in expected_row])
            for (_, a), (_, e) in zip(actual_row, expected_row):
                self.assertAlmostEqual(a, e, places=9)

    def test_local_and_world(self):
        """ローカルは object 空間の長さ、ws=True はワールド空間の長さ。"""
        self.assertIsInstance(self.mesh, Mesh)
        local = self.mesh.getVertexAdjacency()
        self.assertAdjacency(local, self.expected(False))
        self.assertAlmostEqual(local[0][0][1], 2.0)
        world = self.mesh.getVertexAdjacency(worldSpace=True)
        self.assertAdjacency(world, self.expected(True))
        self.assertAlmostEqual(world[0][0][1], 6.0)
        self.assertAdjacency(self.mesh.getVertexAdjacency(worldSpace=True), world)

    def test_units_are_cm(self):
        """UI の距離単位を mm にしても cm の値を返す。"""
        cmds.currentUnit(linear="mm")
        self.assertAlmostEqual(self.mesh.getVertexAdjacency()[0][0][1], 2.0)

    def test_isolated_vertex_is_empty(self):
        """どのエッジにも使われない頂点は空リスト。並びはエッジ番号順。"""
        fn = om2.MFnMesh()
        points = [om2.MPoint(0, 0, 0), om2.MPoint(1, 0, 0), om2.MPoint(1, 0, 1), om2.MPoint(0, 0, 1),
                  om2.MPoint(9, 9, 9)]
        created = fn.create(points, [4], [0, 1, 2, 3])
        transform = cmds.rename(om2.MFnDagNode(created).fullPathName(), self.name("isolated"))
        adjacency = Node(transform).getShape().getVertexAdjacency()
        self.assertEqual(len(adjacency), 5)
        self.assertEqual(adjacency[4], [])
        self.assertEqual(adjacency[3], [(2, 1.0), (0, 1.0)])

    def test_argument_errors(self):
        """bool 以外の空間指定と、worldSpace・ws の同時指定は TypeError。ws は worldSpace と同じ。"""
        self.assertEqual(self.mesh.getVertexAdjacency(ws=True), self.mesh.getVertexAdjacency(worldSpace=True))
        with self.assertRaises(TypeError):
            self.mesh.getVertexAdjacency(worldSpace=True, ws=True)
        with self.assertRaises(TypeError):
            self.mesh.getVertexAdjacency(worldSpace=1)

    def test_num_uvs_is_current_set(self):
        """getNumUVs は現在の UV セットの数。空のセットへ切り替えると0。"""
        self.assertEqual(self.mesh.getNumUVs(), cmds.polyEvaluate(self.plane, uvcoord=True))
        cmds.polyUVSet(self.plane, create=True, uvSet="mlibEmpty")
        cmds.polyUVSet(self.plane, currentUVSet=True, uvSet="mlibEmpty")
        self.assertEqual(self.mesh.getNumUVs(), 0)


if __name__ == "__main__":
    unittest.main()
