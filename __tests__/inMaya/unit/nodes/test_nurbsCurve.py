"""``mlib.nodes.nurbsCurve`` のテスト。

- 形状ラッパーと標準コンストレイントを Maya 内で検証する。
- コントローラー作成の補助(NurbsCurve.create・setCvPositions・Transform.replaceShapes・DagNode.setOverrideColor)の仕様テスト。
- Shape 系(Mesh・NurbsCurve・Camera)とデフォーマー(Cluster)の照会の約束を固定する(担当C)。
- 形状のシェイプのメソッドと createNurbsPlane を確かめる。
"""

import importlib
import math
import sys
import unittest
import uuid

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.nodes import Node, NurbsCurve

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

    def test_nurbs_curve_get_collocated_cv_groups(self):
        curve = mlib.Node(cmds.curve(degree=1, point=[(0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0)]))
        shape = curve.getShape()
        self.assertEqual(shape.getCollocatedCVGroups(), [])

        cmds.move(1, 0, 0, shape.getFullName() + ".cv[2]", absolute=True)
        self.assertEqual(shape.getCollocatedCVGroups(), [[1, 2]])

        cmds.move(1, 0, 0, shape.getFullName() + ".cv[3]", absolute=True)
        self.assertEqual(shape.getCollocatedCVGroups(), [[1, 2, 3]])

        with self.assertRaises(ValueError):
            shape.getCollocatedCVGroups(tolerance=0)


SQUARE = [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)]


def _cvs(shape):
    """cmdsでCVのローカル座標(現在のUI単位)を取得する。"""
    values = cmds.getAttr(shape + ".cv[*]")
    return [tuple(value) for value in values]


def _world_cvs(shape):
    """cmds.xformでCVのワールド座標(現在のUI単位)を取得する。"""
    values = cmds.xform(shape + ".cv[*]", query=True, worldSpace=True, translation=True)
    return [tuple(values[index : index + 3]) for index in range(0, len(values), 3)]


class _Case(NamespaceCase):
    PREFIX = "mlibSpecControls_"
    CLEAR_SELECTION = True

    def curve(self, points=SQUARE, **kwargs):
        """名前空間内にカーブを作成して返す。"""
        kwargs.setdefault("name", self.name("crv#"))
        return mlib.createCurve(points, **kwargs)

    def assertPointsAlmostEqual(self, actual, expected, places=9):
        actual, expected = list(actual), list(expected)
        self.assertEqual(len(actual), len(expected))
        for a, e in zip(actual, expected):
            self.assertSequenceAlmostEqual(tuple(a)[:3], tuple(e)[:3], places=places)


class SetCvPositionsTest(_Case):
    """CV位置の一括書込み。"""

    def test_object_and_world_space_match_cmds(self):
        shape = self.curve(degree=3)
        transform = shape.getTransform().getFullName()
        cmds.setAttr(transform + ".translate", 1, 2, 3)
        cmds.setAttr(transform + ".scale", 2, 2, 2)
        local = [(0, 1, 0), (1, 1, 0), (2, 1, 0), (3, 1, 0)]
        self.assertIs(shape.setCvPositions(local), shape)
        self.assertPointsAlmostEqual(_cvs(shape.getFullName()), local)
        world = [(5, 0, 0), (7, 0, 0), (9, 0, 0), (11, 0, 0)]
        shape.setCvPositions(world, worldSpace=True)
        self.assertPointsAlmostEqual(_world_cvs(shape.getFullName()), world)
        self.assertPointsAlmostEqual(shape.getCvPositions(worldSpace=True), world)

    def test_round_trip_with_get_and_mm_units(self):
        shape = self.curve()
        cmds.currentUnit(linear="mm")
        moved = [om2.MPoint(point.x + 1, point.y, point.z) for point in shape.getCvPositions()]
        shape.setCvPositions(moved)
        cmds.currentUnit(linear="cm")
        self.assertPointsAlmostEqual(_cvs(shape.getFullName()), [(x + 1, y, z) for x, y, z in SQUARE])

    def test_periodic_curve_accepts_both_counts(self):
        shape = self.curve(degree=3, closed=True)
        independent = [(x * 2, y, z * 2) for x, y, z in SQUARE]
        shape.setCvPositions(independent)
        self.assertPointsAlmostEqual(shape.getCvPositions(), independent + independent[:3])
        shape.setCvPositions(independent + independent[:3])
        self.assertEqual(shape.getForm(), om2.MFnNurbsCurve.kPeriodic)
        with self.assertRaises(ValueError):
            shape.setCvPositions(independent + [(9, 9, 9)] + independent[1:3])
        with self.assertRaises(ValueError):
            shape.setCvPositions(independent[:3])

    def test_undo_once(self):
        shape = self.curve()
        self.flushUndo()
        shape.setCvPositions([(0, 5, 0)] * 4)
        self.assertUndoesInOneStep(
            lambda: self.assertPointsAlmostEqual(_cvs(shape.getFullName()), SQUARE),
            lambda: self.assertPointsAlmostEqual(_cvs(shape.getFullName()), [(0, 5, 0)] * 4),
        )

    def test_invalid_inputs(self):
        shape = self.curve()
        for error, args, kwargs in (
            (ValueError, ([(0, 0, 0)] * 3,), {}),
            (ValueError, ([(0, 0, 0)] * 5,), {}),
            (TypeError, ([(0, 0, "a")] * 4,), {}),
            (ValueError, ([(0, 0, float("inf"))] * 4,), {}),
            (TypeError, (SQUARE,), {"worldSpace": 1}),
        ):
            with self.subTest(args=args, kwargs=kwargs):
                with self.assertRaises(error):
                    shape.setCvPositions(*args, **kwargs)
        self.assertPointsAlmostEqual(_cvs(shape.getFullName()), SQUARE)
        # CV単体の書込み(setPosition)も、不正な座標は形状を変えずに拒否する。
        with self.assertRaises(TypeError):
            shape.getCV(0).setPosition((0, 0, "a"))
        self.assertPointsAlmostEqual(_cvs(shape.getFullName()), SQUARE)


class _SpecCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、共通基底からの差分。"""

    PREFIX = "mlibSpecNodeGeo_"
    ENABLE_UNDO = False


class CurveTest(_SpecCase):
    """NurbsCurve の数の照会。"""

    def test_spans_and_form(self):
        """getNumSpans は MFnNurbsCurve.numSpans、getForm は kOpen・kPeriodic の番号。"""
        curve = cmds.curve(degree=3, point=[(0, 0, 0), (1, 1, 0), (2, 0, 0), (3, 1, 0), (4, 0, 0)], name=self.name("open"))
        shape = Node(curve).getShape()
        self.assertIsInstance(shape, NurbsCurve)
        self.assertEqual(shape.getNumSpans(), 2)
        self.assertEqual(shape.getNumSpans(), cmds.getAttr(shape.getFullName() + ".spans"))
        self.assertEqual(shape.getForm(), om2.MFnNurbsCurve.kOpen)
        circle = Node(cmds.circle(name=self.name("circle"), sections=8, constructionHistory=False)[0]).getShape()
        self.assertEqual(circle.getNumSpans(), 8)
        self.assertEqual(circle.getForm(), om2.MFnNurbsCurve.kPeriodic)


class _CaseShapeAdditions(NamespaceCase):
    """形状を作る補助。"""

    PREFIX = "mlibShapeAdd_"

    def surface(self, scale=(1, 1, 1)):
        """幅4・長さ2(lengthRatio 0.5)の NURBS 平面を作り、シェイプのラッパーを返す。"""
        transform = cmds.nurbsPlane(name=self.name("plane#"), width=4, lengthRatio=0.5, patchesU=2, patchesV=1, axis=(0, 1, 0), constructionHistory=False)[0]
        cmds.setAttr(transform + ".translate", 1, 2, 3)
        cmds.setAttr(transform + ".scale", *scale)
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def curve(self, points, degree=3):
        """点列から NURBS カーブを作り、シェイプのラッパーを返す。"""
        transform = cmds.curve(name=self.name("curve#"), point=points, degree=degree)
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def mesh(self):
        """polyPlane(2x2 分割)を作り、シェイプのラッパーを返す。"""
        transform = cmds.polyPlane(name=self.name("mesh#"), subdivisionsX=2, subdivisionsY=2, constructionHistory=False)[0]
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def assertDeletedRaises(self, node, calls):
        """ノードを削除し、各呼出しが RuntimeError になることを確かめる。"""
        cmds.delete(node.getFullName())
        for call in calls:
            with self.subTest(call=call):
                with self.assertRaises(RuntimeError):
                    call(node)


class NurbsCurveAdditionsTest(_CaseShapeAdditions):
    """NurbsCurve のノット・平面判定・面積・作り直し・反転。"""

    POINTS = [(0, 0, 0), (1, 1, 0), (2, 0, 1), (3, 1, 0), (4, 0, 0)]

    def test_knots_and_planar(self):
        """getKnots は getAttr の knots と一致し、isPlanar は平面と立体で変わる。"""
        shape = self.curve(self.POINTS)
        info = cmds.createNode("curveInfo", name=self.name("info#"))
        cmds.connectAttr(shape.getFullName() + ".worldSpace[0]", info + ".inputCurve")
        self.assertSequenceAlmostEqual(shape.getKnots(), cmds.getAttr(info + ".knots")[0])
        self.assertEqual(len(shape.getKnots()), shape.getNumCVs() + shape.getDegree() - 1)
        self.assertFalse(shape.isPlanar())
        flat = self.curve([(0, 0, 0), (1, 0, 1), (2, 0, 0), (3, 0, 2)])
        self.assertTrue(flat.isPlanar())

    def test_area(self):
        """正方形(次数1)は辺の2乗、円は πr² にほぼ等しく、ワールドではスケールを含む。開いたカーブは ValueError。"""
        square = self.curve([(0, 0, 0), (2, 0, 0), (2, 0, 2), (0, 0, 2), (0, 0, 0)], degree=1)
        self.assertAlmostEqual(square.getArea(), 4.0, places=9)
        cmds.setAttr(square.getTransform().getFullName() + ".scale", 3, 1, 2)
        self.assertAlmostEqual(square.getArea(ws=True), 4.0 * 6, places=8)
        circle = mlib.createCircle(radius=2.0, sections=16, name=self.name("circle#"))
        # Maya の円は有理でない近似のため、厳密な πr² とは少し違う。
        self.assertAlmostEqual(circle.getArea(), math.pi * 4, delta=math.pi * 4 * 1e-3)
        with self.assertRaises(ValueError):
            self.curve([(0, 0, 0), (1, 0, 1), (2, 0, 0), (3, 0, 2)]).getArea()
        with self.assertRaises(ValueError):
            self.curve([(0, 0, 0), (2, 0, 0), (2, 1, 2), (0, 0, 2), (0, 0, 0)], degree=1).getArea()
        with self.assertRaises(TypeError):
            square.getArea(worldSpace=True, ws=True)

    def test_rebuild_undo(self):
        """rebuild はスパン・次数・範囲を変え、同じシェイプのノードを保ち、Undo 1回で戻る。"""
        shape = self.curve(self.POINTS)
        uuid = cmds.ls(shape.getFullName(), uuid=True)[0]
        before = shape.getCvPositions()
        start = shape.getPointAtParam(shape.getParamRange()[0])
        self.flushUndo()
        self.assertIs(shape.rebuild(6, keepRange="unit"), shape)
        self.assertUndoesInOneStep(
            lambda: self.assertEqual(len(shape.getCvPositions()), len(before)),
            lambda: (self.assertEqual(shape.getNumSpans(), 6), self.assertEqual(shape.getParamRange(), (0.0, 1.0))),
        )
        self.assertEqual(cmds.ls(uuid)[0], cmds.ls(shape.getFullName())[0])
        shape.rebuild(3, 1, keepRange="spans")
        self.assertEqual(shape.getDegree(), 1)
        self.assertEqual(shape.getNumSpans(), 3)
        self.assertSequenceAlmostEqual(shape.getParamRange(), (0.0, 3.0))
        self.assertSequenceAlmostEqual(shape.getPointAtParam(0.0), start)
        spans = shape.getNumSpans()
        shape.rebuild()
        self.assertEqual(shape.getNumSpans(), spans)
        for args, kwargs, error in (
            ((0,), {}, ValueError),
            ((True,), {}, TypeError),
            ((2.5,), {}, TypeError),
            ((None, 4), {}, ValueError),
            ((None, "3"), {}, TypeError),
            ((), {"keepRange": "keep"}, ValueError),
            ((), {"keepRange": 1}, TypeError),
        ):
            with self.subTest(args=args, kwargs=kwargs):
                with self.assertRaises(error):
                    shape.rebuild(*args, **kwargs)

    def test_reverse_undo(self):
        """reverse は CV の並びを逆にし、Undo 1回で戻る。"""
        shape = self.curve(self.POINTS)
        before = shape.getCvPositions()
        self.flushUndo()
        self.assertIs(shape.reverse(), shape)
        self.assertUndoesInOneStep(
            lambda: self.assertSequenceAlmostEqual([tuple(p) for p in shape.getCvPositions()], [tuple(p) for p in before]),
            lambda: self.assertSequenceAlmostEqual([tuple(p) for p in shape.getCvPositions()], [tuple(p) for p in reversed(before)]),
        )

    def test_empty_and_deleted(self):
        """形状データの無いカーブと削除済みのカーブは RuntimeError。"""
        empty = mlib.createNode("nurbsCurve", name=self.name("empty#"))
        for call in (empty.getKnots, empty.isPlanar, empty.getArea, empty.rebuild, empty.reverse):
            with self.subTest(call=call.__name__):
                with self.assertRaises(RuntimeError):
                    call()
        shape = self.curve(self.POINTS)
        self.assertDeletedRaises(shape, (lambda node: node.getKnots(), lambda node: node.isPlanar(), lambda node: node.rebuild(), lambda node: node.reverse()))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
