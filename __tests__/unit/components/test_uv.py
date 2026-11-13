"""``mlib.components.uv`` のテスト。

- mlib.components の単数・複数コンポーネントの約束を固定する仕様テスト(担当D)。
- 頂点・CV・UVの座標の書込みと、Mesh・NurbsCurve・Transformの形状の反転を確かめる。
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


class UVSpecTest(_ComponentCase):
    """UVの取得を固定する。"""

    def test_uv_positions_match_cmds_and_undo(self):
        """getPosition・getU・getVはpolyEditUVの照会と一致する。"""
        uv = UV(self.mesh, 3)
        expected = cmds.polyEditUV(uv.getFullName(), query=True)
        self.assertPoint(uv.getPosition(), expected)
        self.assertAlmostEqual(uv.getU(), expected[0])
        self.assertAlmostEqual(uv.getV(), expected[1])
        cmds.polyEditUV(uv.getFullName(), relative=False, uValue=1.5, vValue=-0.25)
        self.assertPoint(uv.getPosition(), (1.5, -0.25))

    def test_uvs_bulk(self):
        """UVsは保持順に座標を返す。"""
        uvs = UVs(self.mesh, [1, 0])
        self.assertEqual(uvs.getPosition(), [UV(self.mesh, 1).getPosition(), UV(self.mesh, 0).getPosition()])
        self.assertEqual(uvs.getU(), [UV(self.mesh, 1).getU(), UV(self.mesh, 0).getU()])
        self.assertEqual(uvs.getV(), [UV(self.mesh, 1).getV(), UV(self.mesh, 0).getV()])


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


class _Case(NamespaceCase):
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


class UVTest(_Case):
    """UVの書込み。"""

    def test_set_position_u_v(self):
        shape = self.cube()
        name = shape.getFullName()
        uv = shape.getUV(3)
        self.assertIs(uv.setPosition((0.25, 1.5)), uv)
        self.assertPointsAlmostEqual([_uvs(name)[3]], [(0.25, 1.5)])
        self.assertIs(uv.setU(-0.5), uv)
        self.assertIs(uv.setV(2.0), uv)
        self.assertPointsAlmostEqual([_uvs(name)[3]], [(-0.5, 2.0)])

    def test_collection_setters(self):
        shape = self.cube()
        name = shape.getFullName()
        uvs = shape.getUVs([0, 5, 2])
        self.assertIs(uvs.setPositions([(0.1, 0.2), (0.3, 0.4), (0.5, 0.6)]), uvs)
        values = _uvs(name)
        self.assertPointsAlmostEqual([values[0], values[5], values[2]], [(0.1, 0.2), (0.3, 0.4), (0.5, 0.6)])
        uvs.setU(0.75)
        uvs.setV([1, 2, 3])
        values = _uvs(name)
        self.assertPointsAlmostEqual([values[0], values[5], values[2]], [(0.75, 1), (0.75, 2), (0.75, 3)])
        uvs.setPosition((0.5, 0.5))
        values = _uvs(name)
        self.assertPointsAlmostEqual([values[0], values[5], values[2]], [(0.5, 0.5)] * 3)
        uvs.setPositions(uvs.getPosition())  # getPositionの結果をそのまま渡せる

    def test_writes_the_current_uv_set(self):
        shape = self.cube()
        name = shape.getFullName()
        cmds.polyUVSet(name, copy=True, uvSet="map1", newUVSet="uv2")
        cmds.polyUVSet(name, currentUVSet=True, uvSet="uv2")
        map1 = _uvs(name, "map1")
        for fast in (False, True):
            with self.subTest(fast=fast):
                shape.getUV(1).setPosition((0.9, 0.1), fast=fast)
                shape.getUVs([2]).setU(0.8, fast=fast)
                self.assertPointsAlmostEqual(_uvs(name, "uv2")[1:3], [(0.9, 0.1), (0.8, _uvs(name, "uv2")[2][1])])
                self.assertEqual(_uvs(name, "map1"), map1)

    def test_undo_once(self):
        shape = self.cube()
        name = shape.getFullName()
        self.check_undo(name, lambda: shape.getUV(0).setPosition((0.9, 0.9)), uv=True)
        self.check_undo(name, lambda: shape.getUV(1).setU(0.7), uv=True)
        self.check_undo(name, lambda: shape.getUV(1).setV(0.7), uv=True)
        uvs = shape.getUVs([2, 3])
        self.check_undo(name, lambda: uvs.setPositions([(0.1, 0.1), (0.2, 0.2)]), uv=True)
        self.check_undo(name, lambda: uvs.setPosition((0.3, 0.3)), uv=True)
        self.check_undo(name, lambda: uvs.setU([0.4, 0.5]), uv=True)
        self.check_undo(name, lambda: uvs.setV(0.6), uv=True)

    def test_fast_matches_normal_without_undo(self):
        actions = (
            ("UV.setPosition", lambda shape, fast: shape.getUV(4).setPosition((0.3, 0.7), fast=fast)),
            ("UV.setU", lambda shape, fast: shape.getUV(4).setU(0.3, fast=fast)),
            ("UV.setV", lambda shape, fast: shape.getUV(4).setV(0.3, fast=fast)),
            ("UVs.setPositions", lambda shape, fast: shape.getUVs([1, 4]).setPositions([(0, 1), (1, 0)], fast=fast)),
            ("UVs.setPosition", lambda shape, fast: shape.getUVs([1, 4]).setPosition((0.2, 0.4), fast=fast)),
            ("UVs.setU", lambda shape, fast: shape.getUVs([1, 4]).setU([0.1, 0.9], fast=fast)),
            ("UVs.setV", lambda shape, fast: shape.getUVs([1, 4]).setV(0.6, fast=fast)),
        )
        for label, action in actions:
            with self.subTest(method=label):
                self.check_fast(lambda text: self.cube(text + "#"), action, uv=True)

    def test_invalid_inputs_do_not_change_the_uvs(self):
        shape = self.cube()
        uv = shape.getUV(0)
        uvs = shape.getUVs([0, 1])
        self.check_rejects(shape.getFullName(), (
            (ValueError, lambda: uv.setPosition((1, 2, 3))),
            (TypeError, lambda: uv.setPosition("ab")),
            (ValueError, lambda: uv.setPosition((0, float("inf")))),
            (TypeError, lambda: uv.setU("0.5")),
            (TypeError, lambda: uv.setV(False)),
            (TypeError, lambda: uv.setPosition((0, 0), fast=1)),
            (ValueError, lambda: uvs.setPositions([(0, 0)])),
            (TypeError, lambda: uvs.setPositions([(0, 0), (0, "a")])),
            (TypeError, lambda: uvs.setPositions("abcd")),
            (ValueError, lambda: uvs.setU([1, 2, 3])),
            (TypeError, lambda: uvs.setV("ab")),
        ), uv=True)
        history = self.cube("history", history=True)
        self.check_rejects(history.getFullName(), (
            (NotImplementedError, lambda: history.getUV(0).setPosition((0, 0), fast=True)),
            (NotImplementedError, lambda: history.getUVs([0, 1]).setU(0.5, fast=True)),
        ), uv=True)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
