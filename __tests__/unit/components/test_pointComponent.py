"""``mlib.components.pointComponent`` のテスト。

- mlib.components の単数・複数コンポーネントの約束を固定する仕様テスト(担当D)。
- maths・components のメソッドと、SurfaceCV・LatticePoint・VertexFace のコンポーネント型を確かめる。
- NurbsSurface・Transform・Vector・コンポーネント等のメソッド・引数の名前を確かめる。
- 頂点・CV・UVの座標の書込みと、Mesh・NurbsCurve・Transformの形状の反転を確かめる。
"""

import math
import sys
import unittest
import uuid

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.components import (
    CV,
    CVs,
    Edge,
    Edges,
    Face,
    Faces,
    LatticePoint,
    LatticePoints,
    SurfaceCV,
    SurfaceCVs,
    UV,
    UVs,
    Vertex,
    VertexFace,
    VertexFaces,
    Vertices,
)
from mlib.components.pointComponent import PointComponent, PointComponents
from mlib.core.object import Object
from mlib.maths import EulerRotate, Matrix, Quaternion, Translate, Vector
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


class SingleComponentSpecTest(_ComponentCase):
    """単数コンポーネントの番号検証・名前・比較を固定する。"""

    def test_index_validation(self):
        """boolと整数以外はTypeError、負数・範囲外はIndexError。負数を末尾として扱わない。"""
        self.assertEqual(Vertex(self.mesh, 7).index, 7)
        with self.assertRaises(TypeError):
            Vertex(self.mesh, True)
        with self.assertRaises(TypeError):
            Vertex(self.mesh, 1.0)
        for index in (-1, 8, 100):
            with self.assertRaises(IndexError):
                Vertex(self.mesh, index)
        for cls, valid, invalid in ((Edge, 11, 12), (Face, 5, 6), (UV, 13, 14)):
            self.assertEqual(cls(self.mesh, valid).index, valid)
            with self.assertRaises(IndexError):
                cls(self.mesh, invalid)
        with self.assertRaises(IndexError):
            CV(self.curve, 3)

    def test_class_hierarchy(self):
        """Vertex/CVはPointComponent、Vertices/CVsはPointComponentsの派生。Edge/Face/UVは座標型ではない。"""
        self.assertTrue(issubclass(Vertex, PointComponent))
        self.assertTrue(issubclass(CV, PointComponent))
        self.assertTrue(issubclass(Vertices, PointComponents))
        self.assertTrue(issubclass(CVs, PointComponents))
        for cls in (Edge, Face, UV):
            self.assertFalse(issubclass(cls, PointComponent))

    def test_shape_type_validation(self):
        """meshの型にカーブ、CVにmeshを渡すとTypeError。Shapeラッパー以外もTypeError。"""
        with self.assertRaises(TypeError):
            Vertex(self.curve, 0)
        with self.assertRaises(TypeError):
            CV(self.mesh, 0)
        with self.assertRaises(TypeError):
            Vertex(self.mesh.getFullName(), 0)

    def test_names_and_value_semantics(self):
        """名前は完全パス・種類記号・番号。同じShape・種類・番号なら等しくハッシュも一致する。"""
        prefix = self.mesh.getFullName()
        self.assertEqual(Vertex(self.mesh, 3).getFullName(), prefix + ".vtx[3]")
        self.assertEqual(str(Edge(self.mesh, 2)), prefix + ".e[2]")
        self.assertEqual(Face(self.mesh, 1).getFullName(), prefix + ".f[1]")
        self.assertEqual(UV(self.mesh, 4).getFullName(), prefix + ".map[4]")
        self.assertEqual(CV(self.curve, 1).getFullName(), self.curve.getFullName() + ".cv[1]")
        self.assertTrue(cmds.objExists(Vertex(self.mesh, 3).getFullName()))
        self.assertEqual(Vertex(self.mesh, 3), Vertex(self.mesh, 3))
        self.assertEqual(hash(Vertex(self.mesh, 3)), hash(Vertex(self.mesh, 3)))
        self.assertEqual(len({Vertex(self.mesh, 3), Vertex(self.mesh, 3)}), 1)
        self.assertNotEqual(Vertex(self.mesh, 3), Vertex(self.mesh, 4))
        self.assertNotEqual(Vertex(self.mesh, 0), Face(self.mesh, 0))
        self.assertIs(Vertex(self.mesh, 0).shape, self.mesh)
        self.assertEqual(Vertex(self.mesh, 0).asString(), Vertex(self.mesh, 0).getFullName())

    def test_names_follow_rename(self):
        """名前はキャッシュせず、親の名前変更に追従する。"""
        vertex = Vertex(self.mesh, 0)
        renamed = cmds.rename(self.cube, self.ns + ":renamedCube")
        self.assertIn("renamedCube", vertex.getFullName())
        self.assertTrue(cmds.objExists(vertex.getFullName()))
        del renamed


class PointPositionSpecTest(_ComponentCase):
    """Vertex/CVの座標取得を固定する。"""

    def test_get_position_object_and_world_in_cm(self):
        """getPositionは既定でobject空間、worldSpace/wsでworld空間。UI単位によらずcm。"""
        vertex = Vertex(self.mesh, 0)
        self.assertIsInstance(vertex.getPosition(), Vector)
        self.assertPoint(vertex.getPosition(), self.om2_point(self.mesh, 0))
        self.assertPoint(vertex.getPosition(worldSpace=True), self.om2_point(self.mesh, 0, world=True))
        self.assertPoint(vertex.getPosition(True), cmds.pointPosition(vertex.getFullName(), world=True))
        cmds.currentUnit(linear="mm")
        self.assertPoint(vertex.getPosition(), self.om2_point(self.mesh, 0))
        self.assertAlmostEqual(vertex.getPositionX(), -0.5)
        self.assertAlmostEqual(vertex.getPositionX(worldSpace=True), 9.5)

    def test_space_argument_validation(self):
        """worldSpaceがbool以外、長短名の同時指定はいずれもTypeError。"""
        vertex = Vertex(self.mesh, 0)
        with self.assertRaises(TypeError):
            vertex.getPosition(worldSpace=1)

    def test_cv_positions_match_cmds(self):
        """CVの座標はcmds.pointPositionと一致する。"""
        cv = CV(self.curve, 1)
        self.assertPoint(cv.getPosition(), cmds.pointPosition(cv.getFullName(), local=True))
        self.assertPoint(cv.getPosition(), (1, 2, 3))


class PointCollectionSpecTest(_ComponentCase):
    """Vertices/CVsの保持順・一括取得を固定する。"""

    def test_indices_order_and_duplicates(self):
        """番号は初出順で重複を除いたtuple。Noneは全要素、空列は空集合。"""
        vertices = Vertices(self.mesh, [3, 1, 3, 0])
        self.assertEqual(vertices.indices, (3, 1, 0))
        self.assertEqual(len(vertices), 3)
        self.assertEqual([v.index for v in vertices], [3, 1, 0])
        self.assertEqual(Vertices(self.mesh).indices, tuple(range(8)))
        self.assertEqual(len(Vertices(self.mesh, [])), 0)
        self.assertEqual(Vertices(self.mesh, []).getPosition(), [])
        with self.assertRaises(IndexError):
            Vertices(self.mesh, [0, 8])
        with self.assertRaises(IndexError):
            Vertices(self.mesh, [-1])
        with self.assertRaises(TypeError):
            Vertices(self.curve, [0])

    def test_getitem_and_names(self):
        """添字は保持列の位置で、sliceは同型の部分集合。名前は個別・範囲圧縮の両方を返す。"""
        vertices = Vertices(self.mesh, [0, 1, 2, 5, 3])
        self.assertIsInstance(vertices[0], Vertex)
        self.assertEqual(vertices[-1].index, 3)
        part = vertices[1:3]
        self.assertIs(type(part), Vertices)
        self.assertEqual(part.indices, (1, 2))
        prefix = self.mesh.getFullName()
        self.assertEqual(vertices.getFullNames()[3], prefix + ".vtx[5]")
        self.assertEqual(vertices.getCompactNames(),
                         [prefix + ".vtx[0:2]", prefix + ".vtx[5]", prefix + ".vtx[3]"])
        self.assertEqual(Vertices(self.mesh, []).getCompactNames(), [])
        with self.assertRaises(IndexError):
            vertices[5]

    def test_axis_values_for_collections(self):
        """getPositionY等は保持順のlistで、各要素のgetPositionの成分と一致する。"""
        vertices = Vertices(self.mesh, [1, 0])
        cmds.xform(vertices[0].getFullName(), objectSpace=True, translation=(0.5, 3.0, 1.0))
        cmds.xform(vertices[1].getFullName(), objectSpace=True, translation=(-0.5, 3.0, -1.0))
        self.assertEqual(vertices.getPositionY(), [3.0, 3.0])
        self.assertEqual(vertices.getPositionZ(), [1.0, -1.0])
        self.assertEqual(vertices.getPositionX(worldSpace=True), [v.getPositionX(worldSpace=True) for v in vertices])

    def test_cvs_bulk(self):
        """CVsも保持順に座標を返す。周期CVの対応を保つため名前は範囲へ圧縮しない。"""
        cvs = CVs(self.curve)
        self.assertEqual(len(cvs), 3)
        self.assertPoint(cvs.getPosition()[2], (4, 5, 6))
        prefix = self.curve.getFullName()
        self.assertEqual(cvs.getCompactNames(), [prefix + ".cv[0]", prefix + ".cv[1]", prefix + ".cv[2]"])
        self.assertEqual(cvs.getCompactNames(), cvs.getFullNames())


class PointTypeSpecTest(_ComponentCase):
    """点の位置はすべてVector(単体)またはlist[Vector]で返す。UVは(U, V)のtuple。"""

    def test_point_types(self):
        """Vertex/CV・Vertices/CVs・Mesh.getPoints・NurbsCurve.getCvPositionsの型と値。"""
        cases = [
            ("Vertex", Vertex(self.mesh, 0).getPosition(), self.om2_point(self.mesh, 0)),
            ("CV", CV(self.curve, 1).getPosition(), (1, 2, 3)),
        ]
        for name, value, expected in cases:
            with self.subTest(name=name):
                self.assertIs(type(value), Vector)
                self.assertPoint(value, expected)
        path = om2.MSelectionList().add(self.mesh.getFullName()).getDagPath(0)
        for ws in (False, True):
            space = om2.MSpace.kWorld if ws else om2.MSpace.kObject
            raw = om2.MFnMesh(path).getPoints(space)
            collections = [
                ("Vertices", Vertices(self.mesh, [2, 0]).getPosition(ws), [raw[2], raw[0]]),
                ("Mesh.getPoints", self.mesh.getPoints(worldSpace=ws), list(raw)),
            ]
            for name, values, expected in collections:
                with self.subTest(name=name, worldSpace=ws):
                    self.assertIsInstance(values, list)
                    self.assertTrue(all(type(value) is Vector for value in values))
                    self.assertEqual(len(values), len(expected))
                    for value, point in zip(values, expected):
                        self.assertPoint(value, (point.x, point.y, point.z))
        curve_points = self.curve.getCvPositions()
        self.assertTrue(all(type(value) is Vector for value in curve_points))
        self.assertEqual(curve_points, [(0, 0, 0), (1, 2, 3), (4, 5, 6)])
        self.assertEqual(CVs(self.curve).getPosition(), curve_points)
        self.assertIsInstance(UV(self.mesh, 0).getPosition(), tuple)

    def test_set_points_round_trip_and_undo(self):
        """Mesh.setPointsはgetPointsの結果・tuple列・MPointArrayを受け、1回のUndoで戻る。"""
        before = self.mesh.getPoints()
        moved = [point + (0, 1, 0) for point in before]
        self.assertIs(self.mesh.setPoints(moved), self.mesh)
        self.assertEqual(self.mesh.getPoints(), moved)
        cmds.undo()
        self.assertEqual(self.mesh.getPoints(), before)
        tuples = [(p.x * 2, p.y, p.z) for p in before]
        self.mesh.setPoints(tuples)
        self.assertEqual(self.mesh.getPoints(), tuples)
        cmds.undo()
        array = om2.MPointArray([om2.MPoint(p.x, p.y + 3, p.z) for p in before])
        self.mesh.setPoints(array)
        self.assertEqual(self.mesh.getPoints(), [(p.x, p.y + 3, p.z) for p in before])
        cmds.undo()
        self.assertEqual(self.mesh.getPoints(), before)
        # 未変更の頂点は書き込まない。部分的な変更でも結果は同じ。
        partial = list(before)
        partial[3] = Vector(5, 6, 7)
        self.mesh.setPoints(partial)
        self.assertEqual(self.mesh.getPoints(), partial)
        cmds.undo()
        self.assertEqual(self.mesh.getPoints(), before)

    def test_set_points_world_space_and_units(self):
        """worldSpace=TrueはTransformを含む座標。UI単位によらずcm。"""
        world = self.mesh.getPoints(worldSpace=True)
        cmds.currentUnit(linear="mm")
        target = [point + (0, 0, 1) for point in world]
        self.mesh.setPoints(target, worldSpace=True)
        for actual, expected in zip(self.mesh.getPoints(worldSpace=True), target):
            self.assertPoint(actual, expected)
        for actual, expected in zip(self.mesh.getPoints(), target):
            self.assertPoint(actual, expected - (10, 0, 0))
        cmds.undo()
        for actual, expected in zip(self.mesh.getPoints(worldSpace=True), world):
            self.assertPoint(actual, expected)

    def test_set_points_rejects_invalid_input(self):
        """頂点数違いはValueError、型の誤りはTypeError、非有限はValueError。変更前に拒否する。"""
        before = self.mesh.getPoints()
        for points, error in [(before[:-1], ValueError), (before + [Vector()], ValueError),
                              ([(0, 0)] * 8, ValueError), ([(0, 0, float("nan"))] * 8, ValueError),
                              ("abc", TypeError), (Vector(), TypeError), (5, TypeError),
                              ([("a", 0, 0)] * 8, TypeError)]:
            with self.subTest(points=repr(points)[:40]):
                with self.assertRaises(error):
                    self.mesh.setPoints(points)
        with self.assertRaises(TypeError):
            self.mesh.setPoints(before, worldSpace=1)
        self.assertEqual(self.mesh.getPoints(), before)


def _flat(names):
    """cmds が返す範囲付きの名前を、一件ずつのコンポーネント部分(``e[3]`` 等)の集合にする。

    cmds は Transform 名・Shape 名のどちらで返すこともあるため、ノード名を除いて比べる。
    """
    return {name.rsplit(".", 1)[1] for name in cmds.ls(names, flatten=True)}


def _names(components):
    """コンポーネントの集まりのコンポーネント部分の集合を返す。"""
    return {name.rsplit(".", 1)[1] for name in components.getFullNames()}


class _Case(NamespaceCase):
    """形状を作る補助。"""

    PREFIX = "mlibMathCompAdd_"

    def cube(self):
        """1辺2cm の履歴なし polyCube の (transform名, Mesh) を返す。"""
        transform = cmds.polyCube(name=self.name("cube#"), width=2, height=2, depth=2, constructionHistory=False)[0]
        shape = cmds.listRelatives(transform, shapes=True, fullPath=True)[0]
        return transform, mlib.getNode(shape)

    def plane(self):
        """3x2 分割の履歴なし polyPlane(縁を持つ)の Mesh を返す。"""
        transform = cmds.polyPlane(name=self.name("pp#"), subdivisionsX=3, subdivisionsY=2,
                                   constructionHistory=False)[0]
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def surface(self):
        """2x3 スパン・3次の履歴なし nurbsPlane(tx=1, ty=2)の NurbsSurface を返す。"""
        transform = cmds.nurbsPlane(name=self.name("plane#"), width=4, lengthRatio=1.5, patchesU=2, patchesV=3,
                                    degree=3, axis=(0, 1, 0), constructionHistory=False)[0]
        cmds.setAttr(transform + ".translate", 1, 2, 0)
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def lattice(self, divisions=(2, 3, 4)):
        """cube を変形するラティスを作り、移動・拡大したラティスのシェイプを返す。"""
        transform, _ = self.cube()
        lattice = cmds.lattice(transform, divisions=divisions, objectCentered=True, name=self.name("ffd#"))[1]
        cmds.setAttr(lattice + ".translate", 1, 2, 3)
        cmds.setAttr(lattice + ".scale", 2, 2, 2)
        return mlib.getNode(cmds.listRelatives(lattice, shapes=True, fullPath=True)[0])

    def assertVectorAlmostEqual(self, actual, expected, places=7):
        self.assertSequenceAlmostEqual(list(actual), list(expected), places=places)

    def assertUndoEmpty(self):
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))


class MeshComponentTest(_Case):
    """Vertex・Edge・Face・UV の追加メソッド。"""

    def convert(self, component, **flags):
        return _flat(cmds.polyListComponentConversion(component.getFullName(), **flags))

    def names(self, components):
        return _names(components)

    def test_adjacency_matches_cmds(self):
        _, mesh = self.cube()
        vertex = mesh.getVertex(3)
        self.assertEqual(self.names(vertex.getEdges()), self.convert(vertex, toEdge=True))
        self.assertEqual(list(vertex.getEdges().indices), sorted(vertex.getEdges().indices))
        connected = vertex.getConnectedVertices()
        expected = self.convert(vertex, toEdge=True)
        expected = _flat(cmds.polyListComponentConversion([mesh.getFullName() + "." + part for part in expected],
                                                          toVertex=True))
        expected.discard(vertex.getFullName().rsplit(".", 1)[1])
        self.assertEqual(self.names(connected), expected)
        edge = Edge(mesh, 0)
        neighbors = edge.getConnectedEdges()
        expected = _flat(cmds.polyListComponentConversion(
            [mesh.getFullName() + "." + part for part in self.convert(edge, toVertex=True)], toEdge=True))
        expected.discard(edge.getFullName().rsplit(".", 1)[1])
        self.assertEqual(self.names(neighbors), expected)
        face = Face(mesh, 0)
        expected = _flat(cmds.polyListComponentConversion(
            [mesh.getFullName() + "." + part for part in self.convert(face, toEdge=True)], toFace=True))
        expected.discard(face.getFullName().rsplit(".", 1)[1])
        self.assertEqual(self.names(face.getConnectedFaces()), expected)
        # 複数形は単数のメソッドを要素ごとに呼ぶ。
        self.assertEqual([len(item) for item in mesh.getVertices([0, 1]).getEdges()], [3, 3])

    def test_boundary(self):
        mesh = self.plane()
        border_edges = set(mesh.getBorderEdges().indices)
        border_vertices = set(mesh.getBorderVertices().indices)
        self.assertEqual({e for e in range(mesh.getNumEdges()) if Edge(mesh, e).isOnBoundary()}, border_edges)
        self.assertEqual({v for v in range(mesh.getNumVertices()) if Vertex(mesh, v).isOnBoundary()},
                         border_vertices)
        self.assertEqual(sum(Face(mesh, f).isOnBoundary() for f in range(mesh.getNumPolygons())), 6)
        _, cube = self.cube()
        self.assertFalse(any(cube.getVertices().isOnBoundary()))

    def test_uvs(self):
        _, mesh = self.cube()
        face = Face(mesh, 1)
        uvs = face.getUVs()
        self.assertEqual(self.names(uvs), self.convert(face, toUV=True))
        vertex = mesh.getVertex(0)
        self.assertEqual(self.names(vertex.getUVs()), self.convert(vertex, toUV=True))
        for uv in vertex.getUVs():
            with self.subTest(uv=uv.index):
                self.assertEqual(uv.getVertex(), vertex)
        for index in range(mesh.getNumUVs()):
            with self.subTest(index=index):
                expected = self.convert(UV(mesh, index), toVertex=True)
                self.assertEqual({UV(mesh, index).getVertex().getFullName().rsplit(".", 1)[1]}, expected)
        name = mesh.getFullName()
        cmds.polyMapDel(name + ".f[0]")
        self.assertEqual(len(Face(mesh, 0).getUVs()), 0)

    def test_face_shape_checks(self):
        _, mesh = self.cube()
        face = Face(mesh, 0)
        self.assertTrue(face.isPlanar())
        self.assertTrue(face.isConvex())
        self.assertFalse(face.isLamina())
        self.assertFalse(face.isHoled())
        self.assertFalse(face.isZeroArea())
        self.assertEqual(face.getTriangleCount(), 2)
        self.assertEqual(sum(mesh.getFaces().getTriangleCount()), cmds.polyEvaluate(mesh.getFullName(), triangle=True))
        mesh.getVertex(0).moveBy((0.0, 0.0, 0.5))
        self.assertFalse(face.isPlanar())
        flat = mesh.getVertices(Face(mesh, 1).getVertices().indices)
        flat.setPosition((0.0, 5.0, 0.0))
        self.assertTrue(Face(mesh, 1).isZeroArea())
        self.assertFalse(Face(mesh, 2).isZeroArea())
        self.assertTrue(Face(mesh, 2).isZeroArea(tolerance=100.0))
        with self.assertRaises(ValueError):
            Face(mesh, 2).isZeroArea(-1.0)

    def test_smooth_edges(self):
        _, mesh = self.cube()
        edge = Edge(mesh, 0)
        self.assertFalse(edge.isSmooth())
        self.assertIn("Hard", cmds.polyInfo(edge.getFullName(), edgeToVertex=True)[0])
        self.flushUndo()
        self.assertIs(edge.setSmooth(), edge)
        self.assertUndoesInOneStep(lambda: self.assertFalse(edge.isSmooth()),
                                   lambda: self.assertTrue(edge.isSmooth()))
        self.assertEqual(cmds.listHistory(mesh.getFullName()), [mesh.getFullName().split("|")[-1]])
        edge.setSmooth(True)
        edge.setSmooth(False)
        self.assertFalse(edge.isSmooth())
        with self.assertRaises(TypeError):
            edge.setSmooth(1)
        history_transform = cmds.polyCube(name=self.name("hist#"))[0]
        history = Edge(mlib.getNode(cmds.listRelatives(history_transform, shapes=True, fullPath=True)[0]), 2)
        history.setSmooth(True)
        self.assertTrue(history.isSmooth())

    def test_vertex_color(self):
        _, mesh = self.cube()
        vertex = mesh.getVertex(2)
        self.assertIsNone(vertex.getColor())
        self.flushUndo()
        self.assertIs(vertex.setColor((1.0, 0.5, 0.0)), vertex)
        self.assertSequenceAlmostEqual(vertex.getColor(), (1.0, 0.5, 0.0, 1.0), places=5)
        self.assertSequenceAlmostEqual(cmds.polyColorPerVertex(vertex.getFullName(), query=True, rgb=True),
                                       (1.0, 0.5, 0.0), places=5)
        self.assertIsNone(mesh.getVertex(3).getColor())
        cmds.undo()
        self.assertIsNone(vertex.getColor())
        cmds.redo()
        self.flushUndo()
        vertex.setColor((0.0, 0.0, 1.0, 0.5), fast=True)
        self.assertUndoEmpty()
        self.assertSequenceAlmostEqual(vertex.getColor(), (0.0, 0.0, 1.0, 0.5), places=5)
        for call, error in ((lambda: vertex.setColor((1, 0)), ValueError),
                            (lambda: vertex.getColor(colorSet="missing"), ValueError),
                            (lambda: vertex.setColor((1, 0, 0), fast=1), TypeError)):
            with self.subTest(error=error):
                with self.assertRaises(error):
                    call()

    def test_is_complete(self):
        _, mesh = self.cube()
        self.assertTrue(mesh.getVertices().isComplete())
        self.assertTrue(Vertices(mesh, list(reversed(range(8)))).isComplete())
        self.assertFalse(mesh.getVertices([0, 1]).isComplete())
        self.assertTrue(mesh.getFaces().isComplete())
        self.assertFalse((mesh.getVertices([0]) + mesh.getVertices([1])).isComplete())

    def test_deleted_shape(self):
        transform, mesh = self.cube()
        vertex, edge, face = mesh.getVertex(0), Edge(mesh, 0), Face(mesh, 0)
        vertices = mesh.getVertices([0, 1])
        cmds.delete(transform)
        for call in (vertex.getEdges, vertex.getConnectedVertices, vertex.isOnBoundary, vertex.getUVs,
                     vertex.getColor, edge.isSmooth, edge.getConnectedEdges, face.getUVs, face.isPlanar,
                     face.getTriangleCount, vertices.isComplete):
            with self.subTest(call=call.__name__):
                with self.assertRaises(RuntimeError):
                    call()


class _CaseMethodAdditions(NamespaceCase):
    """形状を作る補助。"""

    PREFIX = "mlibMethodAdd_"

    def surface(self):
        """2x3 スパン・3次の NURBS 平面を作り、シェイプのラッパーを返す。"""
        transform = cmds.nurbsPlane(name=self.name("plane#"), width=4, lengthRatio=1.5, patchesU=2, patchesV=3,
                                    degree=3, axis=(0, 1, 0), constructionHistory=False)[0]
        cmds.setAttr(transform + ".translate", 1, 2, 3)
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def cube(self):
        """1辺2cm の polyCube を作り、(transform, shape) のラッパーを返す。"""
        transform = cmds.polyCube(name=self.name("cube#"), width=2, height=2, depth=2, constructionHistory=False)[0]
        shape = cmds.listRelatives(transform, shapes=True, fullPath=True)[0]
        return mlib.getNode(transform), mlib.getNode(shape)


class MeshComponentQueryTest(_CaseMethodAdditions):
    """Face・Edge・Vertex の幾何の照会。"""

    def test_face_queries(self):
        """面の中心・法線・面積が polyInfo・om2 と一致し、ワールド指定は transform を含む。Faces は各面のリスト。"""
        transform, shape = self.cube()
        cmds.setAttr(transform.getFullName() + ".translate", 0, 5, 0)
        cmds.setAttr(transform.getFullName() + ".scale", 2, 2, 2)
        face = shape.getFace(1)  # polyCube の f[1] は +Y の面。
        self.assertSequenceAlmostEqual(face.getCenter(), (0, 1, 0))
        self.assertSequenceAlmostEqual(face.getCenter(ws=True), (0, 7, 0))
        self.assertSequenceAlmostEqual(face.getNormal(), (0, 1, 0))
        self.assertSequenceAlmostEqual(face.getNormal(worldSpace=True), (0, 1, 0))
        self.assertAlmostEqual(face.getArea(), 4.0)
        self.assertAlmostEqual(face.getArea(worldSpace=True), 16.0)
        centers = shape.getFaces([0, 1]).getCenter()
        self.assertEqual(len(centers), 2)
        self.assertSequenceAlmostEqual(centers[1], (0, 1, 0))

    def test_edge_and_vertex_queries(self):
        """エッジの長さ・中点と頂点の法線(om2 の getVertexNormal と同じ)。"""
        transform, shape = self.cube()
        cmds.setAttr(transform.getFullName() + ".scale", 3, 1, 1)
        edge = shape.getEdge(0)
        a, b = [cmds.pointPosition(f"{shape.getFullName()}.vtx[{i}]", world=True) for i in
                cmds.polyInfo(edge.getFullName(), edgeToVertex=True)[0].split(":")[1].split()[:2]]
        self.assertAlmostEqual(edge.getLength(), 2.0)
        self.assertAlmostEqual(edge.getLength(ws=True), math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b))))
        self.assertSequenceAlmostEqual(edge.getCenter(worldSpace=True), [(x + y) / 2 for x, y in zip(a, b)])
        fn = om2.MFnMesh(shape.mpath())
        for weighted in (False, True):
            with self.subTest(angleWeighted=weighted):
                normal = shape.getVertex(0).getNormal(angleWeighted=weighted)
                expected = om2.MVector(fn.getVertexNormal(0, weighted, om2.MSpace.kObject)).normal()
                self.assertSequenceAlmostEqual(normal, expected)
                self.assertAlmostEqual(normal.length(), 1.0)
        with self.assertRaises(TypeError):
            shape.getVertex(0).getNormal(angleWeighted=1)

    def test_query_errors(self):
        """範囲外の番号は IndexError、worldSpace の型違い・ws との同時指定は TypeError、削除済みは RuntimeError。"""
        transform, shape = self.cube()
        calls = (lambda c, **f: shape.getFace(c).getCenter(**f), lambda c, **f: shape.getFace(c).getNormal(**f),
                 lambda c, **f: shape.getFace(c).getArea(**f), lambda c, **f: shape.getEdge(c).getLength(**f),
                 lambda c, **f: shape.getEdge(c).getCenter(**f), lambda c, **f: shape.getVertex(c).getNormal(**f))
        for number, call in enumerate(calls):
            with self.subTest(call=number):
                with self.assertRaises(IndexError):
                    call(999)
                with self.assertRaises(TypeError):
                    call(0, worldSpace=1)
                with self.assertRaises(TypeError):
                    call(0, worldSpace=True, ws=True)
        face = shape.getFace(0)
        cmds.delete(transform.getFullName())
        with self.assertRaises(RuntimeError):
            face.getCenter()


class PointMoveTest(_CaseMethodAdditions):
    """PointComponent(s).moveBy と PointComponents.getCenter。"""

    def test_move_by_single_and_undo(self):
        """1点の moveBy は相対移動で、Undo 1回で戻り、fast はUndoに残らない。ワールド指定は親の変換を含む。"""
        transform, shape = self.cube()
        vertex = shape.getVertex(2)
        before = vertex.getPosition()
        self.flushUndo()
        self.assertIs(vertex.moveBy((1, 2, 3)), vertex)
        self.assertUndoesInOneStep(
            lambda: self.assertSequenceAlmostEqual(vertex.getPosition(), before),
            lambda: self.assertSequenceAlmostEqual(vertex.getPosition(), mlib.Vector(before) + mlib.Vector(1, 2, 3)))
        cmds.setAttr(transform.getFullName() + ".scale", 2, 2, 2)
        world = vertex.getPosition(worldSpace=True)
        vertex.moveBy((0, 1, 0), ws=True)
        self.assertSequenceAlmostEqual(vertex.getPosition(worldSpace=True), mlib.Vector(world) + mlib.Vector(0, 1, 0))
        self.flushUndo()
        vertex.moveBy((0, -1, 0), worldSpace=True, fast=True)
        self.assertUndoEmpty()
        self.assertSequenceAlmostEqual(vertex.getPosition(worldSpace=True), world)

    def test_move_by_collection_and_center(self):
        """複数の moveBy は全点を同じだけ動かし Undo 1回で戻る。getCenter は位置の平均。CV でも使える。"""
        transform, shape = self.cube()
        top = shape.getVertices([2, 3, 4, 5])
        before = top.getPosition()
        self.assertSequenceAlmostEqual(top.getCenter(), mlib.Vector(sum(p.x for p in before), sum(p.y for p in before),
                                                                    sum(p.z for p in before)) / 4.0)
        self.flushUndo()
        self.assertIs(top.moveBy(om2.MVector(0, 1, 0)), top)
        self.assertUndoesInOneStep(
            lambda: self.assertSequenceAlmostEqual(top.getPosition()[0], before[0]),
            lambda: self.assertSequenceAlmostEqual(top.getPosition()[0], mlib.Vector(before[0]) + mlib.Vector(0, 1, 0)))
        curve = mlib.getNode(cmds.listRelatives(cmds.curve(name=self.name("crv#"), degree=1,
                                                           point=[(0, 0, 0), (2, 0, 0), (2, 4, 0)]),
                                                shapes=True, fullPath=True)[0])
        self.assertSequenceAlmostEqual(curve.getCVs().getCenter(), (4.0 / 3.0, 4.0 / 3.0, 0))
        self.assertEqual(list(shape.getVertices([]).moveBy((1, 0, 0)).indices), [])

    def test_move_by_errors(self):
        """移動量の型・成分数・空の集まりの getCenter の誤りは例外で、位置は変わらない。"""
        transform, shape = self.cube()
        vertices = shape.getVertices([0, 1])
        before = vertices.getPosition()
        for offset, flags, error in (("abc", {}, TypeError), ((1, 2), {}, ValueError),
                                     ((1, 0, float("nan")), {}, ValueError), ((1, 0, 0), {"fast": 1}, TypeError)):
            with self.subTest(offset=offset, flags=flags):
                with self.assertRaises(error):
                    vertices.moveBy(offset, **flags)
                with self.assertRaises(error):
                    vertices[0].moveBy(offset, **flags)
                self.assertSequenceAlmostEqual(vertices.getPosition()[0], before[0])
        with self.assertRaises(ValueError):
            shape.getVertices([]).getCenter()


PLACES = 4


def _path(name):
    """名前からDAGパスを取得する。"""
    selection = om2.MSelectionList()
    selection.add(name)
    return selection.getDagPath(0)


def _points(name, worldSpace=False):
    """MeshまたはNurbsCurveの全点をcmのXYZのlistで返す(mlibを通さない)。"""
    path = _path(name)
    space = om2.MSpace.kWorld if worldSpace else om2.MSpace.kObject
    if path.node().hasFn(om2.MFn.kMesh):
        values = om2.MFnMesh(path).getPoints(space)
    else:
        values = om2.MFnNurbsCurve(path).cvPositions(space)
    return [(point.x, point.y, point.z) for point in values]


def _uvs(name, uvSet=None):
    """現在(または指定)のUVセットの全UVを(u, v)のlistで返す(mlibを通さない)。"""
    fn = om2.MFnMesh(_path(name))
    us, vs = fn.getUVs(uvSet or fn.currentUVSetName())
    return list(zip(us, vs))


def _mirrored(points, indices, axis, pivot):
    """指定番号の点の指定軸を ``2 * pivot - 値`` にした新しい点列を返す。"""
    result = [list(point) for point in points]
    for index in indices:
        result[index][axis] = 2.0 * pivot[axis] - result[index][axis]
    return [tuple(point) for point in result]


class _CaseShapeEditing(NamespaceCase):
    """移動・回転・非一様スケールしたcubeとカーブを作る補助。"""

    def assertPointsAlmostEqual(self, actual, expected, places=PLACES):
        actual, expected = list(actual), list(expected)
        self.assertEqual(len(actual), len(expected))
        for index, (a, e) in enumerate(zip(actual, expected)):
            for axis in range(len(e)):
                self.assertAlmostEqual(a[axis], e[axis], places=places,
                                       msg=f"point {index} axis {axis}: {tuple(a)} != {tuple(e)}")

    def cube(self, text="cube", history=False):
        """移動・回転・非一様スケールしたpolyCubeのShapeを返す。"""
        transform = cmds.polyCube(name=self.name(text), constructionHistory=history)[0]
        cmds.xform(transform, translation=(1, 2, 3), rotation=(10, 30, 45), scale=(2, 1, 0.5))
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def curve(self, text="crv", periodic=False):
        """移動・回転したnurbsCurve(3次)のShapeを返す。periodic=Trueは周期カーブ。"""
        points = [(0, 0, 0), (2, 1, 0), (3, 0, 2), (1, -1, 3), (-1, 0, 2)]
        if periodic:
            transform = cmds.curve(name=self.name(text), degree=3, periodic=True,
                                   point=points + points[:3], knot=list(range(-2, 8)))
        else:
            transform = cmds.curve(name=self.name(text), degree=3, point=points)
        cmds.xform(transform, translation=(-1, 2, 0), rotation=(0, 0, 30), scale=(1, 2, 1))
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def check_undo(self, name, action, uv=False):
        """actionがUndo 1回で戻り、キューに他の項目を残さないことを確かめる。"""
        read = _uvs if uv else _points
        before = read(name)
        self.flushUndo()
        action()
        after = read(name)
        self.assertNotEqual(after, before)
        self.assertUndoesInOneStep(lambda: self.assertPointsAlmostEqual(read(name), before, places=6),
                                   lambda: self.assertPointsAlmostEqual(read(name), after, places=6))

    def check_fast(self, make, action, uv=False):
        """同じ形状の2つへ通常とfastで同じ操作をし、結果の一致とfastがUndoに積まないことを確かめる。"""
        read = _uvs if uv else _points
        normal, fast = make("normal"), make("fast")
        action(normal, False)
        self.flushUndo()
        action(fast, True)
        self.assertUndoEmpty()
        self.assertPointsAlmostEqual(read(fast.getFullName()), read(normal.getFullName()))
        if not uv:
            self.assertPointsAlmostEqual(read(fast.getFullName(), True), read(normal.getFullName(), True))

    def check_rejects(self, name, cases, uv=False):
        """不正な入力が指定の例外型で拒否され、形状を変えないことを確かめる。"""
        read = _uvs if uv else _points
        before = read(name)
        for error, action in cases:
            with self.subTest(error=error.__name__, action=action):
                with self.assertRaises(error):
                    action()
                self.assertEqual(read(name), before)


class PointComponentTest(_CaseShapeEditing):
    """単数の頂点・CVの書込み。"""

    def test_set_position_object_and_world_space(self):
        shape = self.cube()
        name = shape.getFullName()
        vertex = shape.getVertex(2)
        self.assertIs(vertex.setPosition((1.5, -2.0, 0.25)), vertex)
        self.assertPointsAlmostEqual([_points(name)[2]], [(1.5, -2.0, 0.25)])
        vertex.setPosition(om2.MPoint(4, 5, 6), worldSpace=True)
        self.assertPointsAlmostEqual([_points(name, True)[2]], [(4, 5, 6)])
        cv = self.curve().getCV(1)
        cv.setPosition((7, 8, 9), worldSpace=True)
        self.assertPointsAlmostEqual([_points(cv.shape.getFullName(), True)[1]], [(7, 8, 9)])
        cv.setPosition((1, 2, 3))
        self.assertPointsAlmostEqual([_points(cv.shape.getFullName())[1]], [(1, 2, 3)])

    def test_set_position_axis_keeps_other_axes_in_the_same_space(self):
        shape = self.cube()
        name = shape.getFullName()
        vertex = shape.getVertex(3)
        for axis, method in enumerate((vertex.setPositionX, vertex.setPositionY, vertex.setPositionZ)):
            for worldSpace in (False, True):
                with self.subTest(axis=axis, worldSpace=worldSpace):
                    before = list(_points(name, worldSpace)[3])
                    self.assertIs(method(2.5, worldSpace=worldSpace), vertex)
                    before[axis] = 2.5
                    self.assertPointsAlmostEqual([_points(name, worldSpace)[3]], [before])

    def test_values_are_cm_regardless_of_the_linear_unit(self):
        shape = self.cube()
        name = shape.getFullName()
        cmds.currentUnit(linear="m")
        shape.getVertex(0).setPosition((100, 0, 0))
        shape.getVertex(1).setPositionY(50)
        points = _points(name)
        self.assertPointsAlmostEqual([points[0]], [(100, 0, 0)])
        self.assertAlmostEqual(points[1][1], 50, places=PLACES)
        self.assertAlmostEqual(shape.getVertex(0).getPositionX(), 100, places=PLACES)
        curve = self.curve()
        curve.getCV(0).setPosition((10, 20, 30), worldSpace=True)
        self.assertPointsAlmostEqual([_points(curve.getFullName(), True)[0]], [(10, 20, 30)])

    def test_undo_once(self):
        shape = self.cube()
        name = shape.getFullName()
        vertex = shape.getVertex(4)
        self.check_undo(name, lambda: vertex.setPosition((3, 3, 3)))
        self.check_undo(name, lambda: vertex.setPosition((3, 1, 3), worldSpace=True))
        self.check_undo(name, lambda: vertex.setPositionX(-4))
        self.check_undo(name, lambda: vertex.setPositionY(-4, worldSpace=True))
        self.check_undo(name, lambda: vertex.setPositionZ(-4))
        curve = self.curve()
        self.check_undo(curve.getFullName(), lambda: curve.getCV(2).setPosition((5, 5, 5), worldSpace=True))

    def test_fast_matches_normal_without_undo(self):
        for method, args in (("setPosition", ((1, 2, 3),)), ("setPositionX", (4.0,)), ("setPositionY", (-1.0,)),
                             ("setPositionZ", (0.5,))):
            for worldSpace in (False, True):
                with self.subTest(method=method, worldSpace=worldSpace):
                    self.check_fast(
                        lambda text: self.cube(text + "#"),
                        lambda shape, fast: getattr(shape.getVertex(5), method)(*args, worldSpace=worldSpace,
                                                                                fast=fast))
                    self.check_fast(
                        lambda text: self.curve(text + "#"),
                        lambda shape, fast: getattr(shape.getCV(1), method)(*args, worldSpace=worldSpace,
                                                                            fast=fast))

    def test_fast_periodic_curve_keeps_overlapping_cvs(self):
        curve = self.curve(periodic=True)
        name = curve.getFullName()
        count = len(_points(name))
        curve.getCV(count - 1).setPosition((9, 9, 9), fast=True)  # 末尾の重複CVは先頭の独立CVを書く
        points = _points(name)
        self.assertPointsAlmostEqual([points[2], points[count - 1]], [(9, 9, 9), (9, 9, 9)])

    def test_invalid_inputs_do_not_change_the_shape(self):
        shape = self.cube()
        vertex = shape.getVertex(0)
        self.check_rejects(shape.getFullName(), (
            (TypeError, lambda: vertex.setPosition("abc")),
            (TypeError, lambda: vertex.setPosition(1.0)),
            (ValueError, lambda: vertex.setPosition((1, 2))),
            (ValueError, lambda: vertex.setPosition((1, 2, float("inf")))),
            (TypeError, lambda: vertex.setPosition((1, 2, 3), worldSpace=1)),
            (TypeError, lambda: vertex.setPosition((1, 2, 3), fast=1)),
            (TypeError, lambda: vertex.setPosition((1, 2, 3), worldSpace=True, ws=True)),
            (TypeError, lambda: vertex.setPositionX("1")),
            (TypeError, lambda: vertex.setPositionY(True)),
            (ValueError, lambda: vertex.setPositionZ(float("nan"))),
        ))

    def test_fast_rejects_input_history_and_singular_world_matrix(self):
        shape = self.cube(history=True)
        self.check_rejects(shape.getFullName(), (
            (NotImplementedError, lambda: shape.getVertex(0).setPosition((1, 2, 3), fast=True)),
        ))
        flat = self.cube("flat")
        cmds.setAttr(flat.getTransform().getFullName() + ".scaleX", 0)
        self.check_rejects(flat.getFullName(), (
            (ValueError, lambda: flat.getVertex(0).setPosition((1, 2, 3), worldSpace=True)),
            (ValueError, lambda: flat.getVertex(0).setPosition((1, 2, 3), worldSpace=True, fast=True)),
        ))


class PointComponentsTest(_CaseShapeEditing):
    """頂点・CVの集まりの書込み。"""

    def test_set_positions_and_set_position(self):
        shape = self.cube()
        name = shape.getFullName()
        vertices = shape.getVertices([5, 1, 3])
        rows = [(1, 0, 0), (0, 2, 0), (0, 0, 3)]
        self.assertIs(vertices.setPositions(rows), vertices)
        points = _points(name)
        self.assertPointsAlmostEqual([points[5], points[1], points[3]], rows)
        vertices.setPositions(rows, worldSpace=True)
        points = _points(name, True)
        self.assertPointsAlmostEqual([points[5], points[1], points[3]], rows)
        vertices.setPosition((7, 7, 7), worldSpace=True)
        points = _points(name, True)
        self.assertPointsAlmostEqual([points[5], points[1], points[3]], [(7, 7, 7)] * 3)
        vertices.setPositions(vertices.getPosition())  # getPositionの結果をそのまま渡せる

    def test_set_position_axis_accepts_a_scalar_or_values(self):
        shape = self.curve()
        name = shape.getFullName()
        cvs = shape.getCVs([0, 2])
        for worldSpace in (False, True):
            with self.subTest(worldSpace=worldSpace):
                before = _points(name, worldSpace)
                cvs.setPositionY(1.5, worldSpace=worldSpace)
                cvs.setPositionZ([-1, -2], worldSpace=worldSpace)
                expected = [list(point) for point in before]
                expected[0][1:] = [1.5, -1]
                expected[2][1:] = [1.5, -2]
                self.assertPointsAlmostEqual(_points(name, worldSpace), expected)
        cvs.setPositionX((3, 4))
        self.assertEqual([round(x, 6) for x in cvs.getPositionX()], [3, 4])

    def test_values_are_cm_regardless_of_the_linear_unit(self):
        shape = self.cube()
        name = shape.getFullName()
        cmds.currentUnit(linear="m")
        shape.getVertices([0, 1]).setPositions([(100, 0, 0), (0, 200, 0)], worldSpace=True)
        self.assertPointsAlmostEqual(_points(name, True)[:2], [(100, 0, 0), (0, 200, 0)])
        before = _points(name)
        shape.getVertices([2, 3]).mirror("x", pivot=(50, 0, 0))
        self.assertPointsAlmostEqual(_points(name), _mirrored(before, [2, 3], 0, (50, 0, 0)))

    def test_mirror_subset(self):
        for worldSpace in (False, True):
            with self.subTest(worldSpace=worldSpace):
                shape = self.cube("cube#")
                name = shape.getFullName()
                before = _points(name, worldSpace)
                vertices = shape.getVertices([0, 2, 4])
                self.assertIs(vertices.mirror("XZ", worldSpace=worldSpace, pivot=(0, 1, 0)), vertices)
                self.assertPointsAlmostEqual(_points(name, worldSpace), _mirrored(before, [0, 2, 4], 1, (0, 1, 0)))

    def test_empty_collection_validates_but_does_nothing(self):
        shape = self.cube()
        empty = shape.getVertices([])
        self.flushUndo()
        self.assertIs(empty.setPositions([]), empty)
        self.assertIs(empty.setPosition((1, 2, 3)), empty)
        self.assertIs(empty.mirror(), empty)
        self.assertUndoEmpty()
        with self.assertRaises(ValueError):
            empty.setPosition((1, 2))
        with self.assertRaises(ValueError):
            empty.mirror("w")

    def test_undo_once(self):
        shape = self.cube()
        name = shape.getFullName()
        vertices = shape.getVertices([0, 1, 6])
        self.check_undo(name, lambda: vertices.setPositions([(1, 1, 1), (2, 2, 2), (3, 3, 3)]))
        self.check_undo(name, lambda: vertices.setPosition((4, 4, 4), worldSpace=True))
        self.check_undo(name, lambda: vertices.setPositionX(5))
        self.check_undo(name, lambda: vertices.setPositionY([1, 2, 3], worldSpace=True))
        self.check_undo(name, lambda: vertices.setPositionZ(-1))
        self.check_undo(name, lambda: vertices.mirror("z", pivot=(0, 0, 1)))
        curve = self.curve(periodic=True)
        self.check_undo(curve.getFullName(), lambda: curve.getCVs().mirror("y", worldSpace=True))

    def test_fast_matches_normal_without_undo(self):
        actions = (
            ("setPositions", lambda items, ws, fast: items.setPositions([(1, 2, 3), (4, 5, 6)], worldSpace=ws,
                                                                        fast=fast)),
            ("setPosition", lambda items, ws, fast: items.setPosition((1, 2, 3), worldSpace=ws, fast=fast)),
            ("setPositionX", lambda items, ws, fast: items.setPositionX([1, 2], worldSpace=ws, fast=fast)),
            ("setPositionY", lambda items, ws, fast: items.setPositionY(3, worldSpace=ws, fast=fast)),
            ("setPositionZ", lambda items, ws, fast: items.setPositionZ(-3, worldSpace=ws, fast=fast)),
            ("mirror", lambda items, ws, fast: items.mirror("x", worldSpace=ws, pivot=(1, 0, 0), fast=fast)),
        )
        for label, action in actions:
            for worldSpace in (False, True):
                with self.subTest(method=label, worldSpace=worldSpace):
                    self.check_fast(lambda text: self.cube(text + "#"),
                                    lambda shape, fast: action(shape.getVertices([1, 6]), worldSpace, fast))
                    self.check_fast(lambda text: self.curve(text + "#"),
                                    lambda shape, fast: action(shape.getCVs([0, 3]), worldSpace, fast))
                    self.check_fast(lambda text: self.curve(text + "#", periodic=True),
                                    lambda shape, fast: action(shape.getCVs([1, 6]), worldSpace, fast))

    def test_invalid_inputs_do_not_change_the_shape(self):
        shape = self.cube()
        vertices = shape.getVertices([0, 1])
        self.check_rejects(shape.getFullName(), (
            (ValueError, lambda: vertices.setPositions([(1, 2, 3)])),
            (TypeError, lambda: vertices.setPositions([(1, 2, 3), (1, 2, "a")])),
            (ValueError, lambda: vertices.setPositions([(1, 2, 3), (1, 2, float("inf"))])),
            (TypeError, lambda: vertices.setPositions(5)),
            (ValueError, lambda: vertices.setPosition((1, 2, 3, 4))),
            (ValueError, lambda: vertices.setPositionX([1, 2, 3])),
            (TypeError, lambda: vertices.setPositionX("ab")),
            (TypeError, lambda: vertices.setPositionY([1, None])),
            (TypeError, lambda: vertices.setPositions([(1, 2, 3)] * 2, worldSpace="yes")),
            (TypeError, lambda: vertices.setPositions([(1, 2, 3)] * 2, fast=None)),
            (ValueError, lambda: vertices.mirror("q")),
            (TypeError, lambda: vertices.mirror(None)),
            (ValueError, lambda: vertices.mirror("x", pivot=(1, 2))),
            (ValueError, lambda: vertices.mirror("x", pivot=5)),
            (TypeError, lambda: vertices.mirror("x", worldSpace=1)),
            (TypeError, lambda: vertices.mirror("x", fast="no")),
        ))

    def test_fast_rejects_input_history(self):
        shape = self.cube(history=True)
        self.check_rejects(shape.getFullName(), (
            (NotImplementedError, lambda: shape.getVertices([0, 1]).setPositions([(0, 0, 0)] * 2, fast=True)),
            (NotImplementedError, lambda: shape.getVertices([0, 1]).mirror(fast=True)),
        ))
        # 通常経路は入力履歴があってもtweakとして書き込める。
        shape.getVertices([0]).setPosition((3, 3, 3))
        self.assertPointsAlmostEqual([_points(shape.getFullName())[0]], [(3, 3, 3)])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
