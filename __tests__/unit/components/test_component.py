"""``mlib.components.component`` のテスト。

- mlib.components の単数・複数コンポーネントの約束を固定する仕様テスト(担当D)。
"""

import sys
import unittest
import uuid

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.components import CV, CVs, Edge, Edges, Face, Faces, UV, UVs, Vertex, Vertices
from mlib.components.pointComponent import PointComponent, PointComponents
from mlib.maths import Vector


def _shape(transform):
    """transformの最初のShapeをmlibのラッパーで返す。"""
    return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])


class _ComponentCase(unittest.TestCase):
    """一時名前空間に履歴なしの立方体・履歴付きの立方体・カーブを作る共通の準備。"""

    def setUp(self):
        """テスト用のジオメトリとUI単位・Undo設定を保存する。"""
        self.linear = cmds.currentUnit(query=True, linear=True)
        self.undo_state = cmds.undoInfo(query=True, state=True)
        cmds.undoInfo(stateWithoutFlush=True)
        self.ns = "mlibSpecDComp_" + uuid.uuid4().hex[:8]
        cmds.namespace(add=self.ns)
        self.cube = cmds.polyCube(name=self.ns + ":cube", constructionHistory=False)[0]
        cmds.xform(self.cube, translation=(10, 0, 0))
        self.mesh = _shape(self.cube)
        self.history_cube = cmds.polyCube(name=self.ns + ":history")[0]
        self.history_mesh = _shape(self.history_cube)
        curve = cmds.curve(name=self.ns + ":curve", degree=1, point=[(0, 0, 0), (1, 2, 3), (4, 5, 6)])
        self.curve = _shape(curve)

    def tearDown(self):
        """作成物を削除し、UI単位とUndo設定を戻す。"""
        cmds.currentUnit(linear=self.linear)
        cmds.namespace(removeNamespace=self.ns, deleteNamespaceContent=True)
        cmds.undoInfo(state=self.undo_state)

    def assertPoint(self, actual, expected, places=6):
        """XYZの各成分がほぼ一致することを確かめる。"""
        self.assertEqual(len(actual), len(expected))
        for a, b in zip(actual, expected):
            self.assertAlmostEqual(a, b, places=places)

    def om2_point(self, shape, index, world=False):
        """OpenMayaで頂点座標をcmで独立に求める。"""
        path = om2.MSelectionList().add(shape.getFullName()).getDagPath(0)
        space = om2.MSpace.kWorld if world else om2.MSpace.kObject
        point = om2.MFnMesh(path).getPoint(index, space)
        return (point.x, point.y, point.z)


class ComponentCollectionOperatorSpecTest(_ComponentCase):
    """Components の ``+``・``==``・sort。"""

    def test_add(self):
        """同じシェイプ・同じ種類どうしの+は左辺の型で、重複は初出を残す。"""
        a, b = Vertices(self.mesh, [3, 1]), Vertices(self.mesh, [1, 5])
        joined = a + b
        self.assertIs(type(joined), Vertices)
        self.assertEqual(joined.indices, (3, 1, 5))
        self.assertEqual(a.indices, (3, 1))
        self.assertEqual((a + [Vertex(self.mesh, 0)]).indices, (3, 1, 0))
        self.assertEqual(([Vertex(self.mesh, 0)] + a).indices, (0, 3, 1))
        self.assertEqual((CVs(self.curve, [2]) + CVs(self.curve, [0])).indices, (2, 0))
        for other in (Edges(self.mesh, [0]), Vertices(self.history_mesh, [0]), [Edge(self.mesh, 0)],
                      [Vertex(self.history_mesh, 0)], ["x"]):
            with self.subTest(other=repr(other)):
                with self.assertRaises(TypeError):
                    a + other
        with self.assertRaises(TypeError):
            a + 1

    def test_equality(self):
        """同じシェイプ・種類・番号の並びなら等しい。list・tupleとは要素ごとに比べる。"""
        a = Vertices(self.mesh, [0, 2])
        self.assertEqual(a, Vertices(self.mesh, [0, 2]))
        self.assertNotEqual(a, Vertices(self.mesh, [2, 0]))
        self.assertNotEqual(a, Vertices(self.history_mesh, [0, 2]))
        self.assertNotEqual(a, Faces(self.mesh, [0, 2]))
        self.assertEqual(a, [Vertex(self.mesh, 0), Vertex(self.mesh, 2)])
        self.assertEqual(a, (Vertex(self.mesh, 0), Vertex(self.mesh, 2)))
        self.assertNotEqual(a, [Vertex(self.mesh, 0)])
        self.assertEqual(Vertices(self.mesh, []), [])
        with self.assertRaises(TypeError):
            hash(a)

    def test_sort(self):
        """sortはその場で並べ替えて自身を返す。keyは単数コンポーネントを受ける。別のコレクションは変えない。"""
        a = Vertices(self.mesh, [5, 0, 3])
        part = a[:]
        self.assertIs(a.sort(), a)
        self.assertEqual(a.indices, (0, 3, 5))
        self.assertEqual(part.indices, (5, 0, 3))
        a.sort(reverse=True)
        self.assertEqual(a.indices, (5, 3, 0))
        a.sort(key=lambda vertex: vertex.getPositionX())
        xs = [vertex.getPositionX() for vertex in a]
        self.assertEqual(xs, sorted(xs))
        with self.assertRaises(TypeError):
            a.sort(key=1)
        with self.assertRaises(TypeError):
            a.sort(reverse=1)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
