"""``mlib.components.edge`` のテスト。

- mlib.components の単数・複数コンポーネントの約束を固定する仕様テスト(担当D)。
- スキンのウェイト編集向けの照会・編集の契約を固定する。
"""

import math
import sys
import unittest
import uuid

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.common import Selection
from mlib.components import CV, CVs, Edge, Edges, Face, Faces, UV, UVs, Vertex, Vertices
from mlib.components.pointComponent import PointComponent, PointComponents
from mlib.maths import Vector
from mlib.nodes import GeometryFilter, Joint, SkinCluster
from support.namespaceCase import NamespaceCase


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


class TopologySpecTest(_ComponentCase):
    """トポロジー変更後・削除後の扱いを固定する。"""

    def test_index_out_of_range_after_topology_change(self):
        """要素が減って範囲外になった番号はisValid()がFalseで、操作はIndexError。"""
        vertex = Vertex(self.history_mesh, 7)
        vertices = Vertices(self.history_mesh, [0, 7])
        cmds.delete(self.history_mesh.getFullName() + ".f[0:4]")
        self.assertLess(self.history_mesh.getNumVertices(), 8)
        self.assertFalse(vertex.isValid())
        self.assertFalse(vertices.isValid())
        self.assertEqual(vertex.index, 7)
        with self.assertRaises(IndexError):
            vertex.getPosition()
        with self.assertRaises(IndexError):
            vertices.getPosition()
        with self.assertRaises(IndexError):
            vertex.getFullName()

    def test_deleted_shape(self):
        """削除済みShapeのコンポーネントはisValid()がFalseで、照会はRuntimeError。"""
        vertex = Vertex(self.mesh, 0)
        face = Face(self.mesh, 0)
        cmds.delete(self.cube)
        self.assertFalse(vertex.isValid())
        with self.assertRaises(RuntimeError):
            vertex.getPosition()
        with self.assertRaises(RuntimeError):
            face.getVertices()


class EdgeFaceSpecTest(_ComponentCase):
    """Edge/Faceの頂点と、Faceの割り当て照会を固定する。"""

    def mesh_fn(self):
        """履歴なし立方体のMFnMeshを返す。"""
        return om2.MFnMesh(om2.MSelectionList().add(self.mesh.getFullName()).getDagPath(0))

    def test_vertices_match_om2(self):
        """Edge/Face.getVerticesはMFnMeshの接続順、複数形は保持順で重複を除く。"""
        fn = self.mesh_fn()
        self.assertEqual(Edge(self.mesh, 5).getVertices().indices, tuple(fn.getEdgeVertices(5)))
        self.assertEqual(Face(self.mesh, 2).getVertices().indices, tuple(fn.getPolygonVertices(2)))
        self.assertIs(type(Face(self.mesh, 2).getVertices()), Vertices)
        expected = []
        for face in (2, 0):
            for index in fn.getPolygonVertices(face):
                if index not in expected:
                    expected.append(index)
        self.assertEqual(Faces(self.mesh, [2, 0]).getVertices().indices, tuple(expected))
        expected = []
        for edge in (5, 1):
            for index in fn.getEdgeVertices(edge):
                if index not in expected:
                    expected.append(index)
        self.assertEqual(Edges(self.mesh, [5, 1]).getVertices().indices, tuple(expected))

    def test_shading_engine_and_material(self):
        """getShadingEngineはフェースごとの割り当て、getMaterialはそのサーフェスシェーダー。"""
        shader = cmds.shadingNode("lambert", asShader=True, name=self.ns + ":lambert")
        group = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=self.ns + ":lambertSG")
        cmds.connectAttr(shader + ".outColor", group + ".surfaceShader")
        cmds.sets(self.mesh.getFullName() + ".f[1]", edit=True, forceElement=group)
        assigned = Face(self.mesh, 1).getShadingEngine()
        self.assertEqual(assigned.getName(), group)
        self.assertEqual(Face(self.mesh, 1).getMaterial().getName(), shader)
        default = Face(self.mesh, 0).getShadingEngine()
        self.assertEqual(default.getName(), "initialShadingGroup")
        engines = Faces(self.mesh, [0, 1, 2]).getShadingEngines()
        self.assertEqual([item.getName() for item in engines], ["initialShadingGroup", group])
        materials = Faces(self.mesh, [1, 0, 1]).getMaterials()
        self.assertEqual(materials[0].getName(), shader)
        self.assertEqual(len(materials), 2)

    def test_unassigned_face_returns_none(self):
        """割り当てのないフェースはNoneを返し、複数形の結果には含めない。"""
        cmds.sets(self.mesh.getFullName(), edit=True, remove="initialShadingGroup")
        cmds.sets(self.mesh.getFullName() + ".f[*]", edit=True, remove="initialShadingGroup")
        self.assertIsNone(Face(self.mesh, 0).getShadingEngine())
        self.assertIsNone(Face(self.mesh, 0).getMaterial())
        self.assertEqual(Faces(self.mesh, [0, 1]).getShadingEngines(), [])
        self.assertEqual(Faces(self.mesh, [0, 1]).getMaterials(), [])


def _distance(first, second):
    """2点の距離(Python 3.7 には math.dist が無いため)。"""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(first, second)))


class _SkinCase(NamespaceCase):
    """root→mid→tip の chain と、それにバインドした円柱を作る。"""

    def chain(self):
        cmds.select(clear=True)
        self.root = cmds.joint(name=self.name("root"), position=(0, -2, 0))
        self.mid = cmds.joint(name=self.name("mid"), position=(0, 0, 0))
        self.tip = cmds.joint(name=self.name("tip"), position=(0, 2, 0))
        cmds.select(clear=True)
        return [self.root, self.mid, self.tip]

    def skinned(self, max_influences=3):
        joints = self.chain()
        self.mesh = cmds.polyCylinder(name=self.name("geo"), height=4, subdivisionsHeight=8)[0]
        self.skin = SkinCluster(cmds.skinCluster(joints, self.mesh, toSelectedBones=True,
                                                 maximumInfluences=max_influences)[0])
        cmds.select(clear=True)
        return self.skin

    def raw(self, skin=None):
        skin = skin or self.skin
        return [round(value, 6) for value in skin.getWeights([self.root, self.mid, self.tip])]


class ComponentTopologyTest(_SkinCase):

    def test_grow_shrink(self):
        """grow は cmds の頂点→エッジ→頂点の変換と同じ。shrink は縁を外す。選択は変えない。"""
        plane = cmds.polyPlane(name=self.name("p"), subdivisionsX=4, subdivisionsY=4)[0]
        mesh = mlib.getNode(plane).getShape()
        cmds.select(clear=True)
        vertices = mesh.getVertices([12])
        grown = vertices.grow()
        edges = cmds.polyListComponentConversion(plane + ".vtx[12]", fromVertex=True, toEdge=True)
        expected = cmds.ls(cmds.polyListComponentConversion(edges, fromEdge=True, toVertex=True), flatten=True)
        self.assertEqual(sorted(grown.indices), sorted(int(name.split("[")[-1][:-1]) for name in expected))
        self.assertEqual(grown.indices[0], 12)
        self.assertEqual(grown.shrink().indices, (12,))
        self.assertEqual(vertices.shrink().indices, ())
        self.assertEqual(cmds.ls(selection=True), [])

    def test_loop_ring_match_cmds(self):
        """内部・縁のエッジのループとリングは cmds.polySelect と同じ集合(縁のエッジのループは自身だけ)。"""
        plane = cmds.polyPlane(name=self.name("p"), subdivisionsX=5, subdivisionsY=4)[0]
        cylinder = cmds.polyCylinder(name=self.name("c"), subdivisionsAxis=8, subdivisionsHeight=3)[0]
        for name in (plane, cylinder):
            mesh = mlib.getNode(name).getShape()
            for edge in range(0, mesh.getNumEdges(), 3):
                with self.subTest(mesh=name, edge=edge):
                    loop = cmds.polySelect(name, edgeLoop=edge, noSelection=True) or []
                    ring = cmds.polySelect(name, edgeRing=edge, noSelection=True) or []
                    self.assertEqual(sorted(mesh.getEdge(edge).getLoop().indices), sorted(set(loop)))
                    self.assertEqual(sorted(mesh.getEdges([edge]).getRing().indices), sorted(set(ring)))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
