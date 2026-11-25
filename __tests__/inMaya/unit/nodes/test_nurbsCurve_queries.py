"""NurbsCurve の照会(最近点・パラメーター・弧長・等間隔の点とマトリクス)の契約を固定する。

- getClosestPoint は nearestPointOnCurve、getAtParam(what="point"・"tangent"・"normal")は
  pointOnCurveInfo、getLength(param) は arcLengthDimension と突き合わせる(ローカル・ワールドの両方)。
- getParam(length=)・getParamsAlong は弧長の往復で確かめ、閉じたカーブは終点を含めない。
- getLength・getParam・getAtParam の、同時に指定できない引数と種類の名前の違いの例外型。
- getMatricesAlong は正規直交・右手系・接線と位置・up の向き・平行移動のねじれの無さを確かめる。
- どれもシーンにノードを作らず、Undo キューに積まない読み取り。不正入力の例外型。
"""

import math
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()
from support.namespaceCase import NamespaceCase

from mlib.maths import Matrix, Vector
from mlib.nodes import NurbsCurve


def _distance(first, second):
    """2点の距離(Python 3.7 には math.dist が無いため)。"""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(first, second)))


def _dot(first, second):
    return sum(a * b for a, b in zip(first, second))


def _row(matrix, index):
    return [matrix[index * 4 + column] for column in range(3)]


class _CurveCase(NamespaceCase):
    """親の変換(非均等スケール・回転・移動)の下にある3次の開いたカーブと、円を作る。"""

    def setUp(self):
        super().setUp()
        self.parent = cmds.createNode("transform", name=self.name("grp"))
        cmds.setAttr(self.parent + ".translate", 1, 2, 3)
        cmds.setAttr(self.parent + ".rotate", 10, 30, -20)
        cmds.setAttr(self.parent + ".scale", 1, 2, 0.5)
        transform = cmds.curve(name=self.name("crv"), degree=3, point=[(0, 0, 0), (2, 3, 1), (5, -1, 2), (7, 2, -1), (9, 0, 0)])
        transform = cmds.parent(transform, self.parent)[0]
        self.shape = cmds.listRelatives(transform, shapes=True, fullPath=True)[0]
        self.curve = mlib.getNode(self.shape)
        circle = cmds.circle(name=self.name("circle"), normal=(0, 1, 0), radius=3)[0]
        self.circle_shape = cmds.listRelatives(circle, shapes=True, fullPath=True)[0]
        self.circle = mlib.getNode(self.circle_shape)

    def poci(self, shape, param, world):
        node = cmds.createNode("pointOnCurveInfo", name=self.name("poci#"))
        cmds.connectAttr(shape + (".worldSpace[0]" if world else ".local"), node + ".inputCurve")
        cmds.setAttr(node + ".parameter", param)
        return node

    def assertVector(self, actual, expected, places=5):
        self.assertLess(_distance(actual, expected), 10**-places, (tuple(actual), tuple(expected)))


class ParamTest(_CurveCase):
    def test_class_and_param_range(self):
        """NurbsCurve として取得し、範囲は minValue・maxValue と同じ。"""
        self.assertIsInstance(self.curve, NurbsCurve)
        start, end = self.curve.getParamRange()
        self.assertEqual((start, end), (cmds.getAttr(self.shape + ".minValue"), cmds.getAttr(self.shape + ".maxValue")))
        self.assertEqual(self.circle.getParamRange(), (0.0, 8.0))

    def test_point_tangent_normal_match_point_on_curve_info(self):
        """位置・正規化した接線・法線は pointOnCurveInfo と一致する(ローカル・ワールド)。"""
        for world in (False, True):
            for param in (0.0, 0.3, 1.0, 1.7, 2.0):
                with self.subTest(world=world, param=param):
                    node = self.poci(self.shape, param, world)
                    point = self.curve.getAtParam(param, worldSpace=world)
                    self.assertIsInstance(point, Vector)
                    self.assertVector(point, cmds.getAttr(node + ".position")[0])
                    tangent = self.curve.getAtParam(param, worldSpace=world, what="tangent")
                    self.assertIsInstance(tangent, Vector)
                    self.assertAlmostEqual(tangent.length(), 1.0, places=9)
                    self.assertVector(tangent, cmds.getAttr(node + ".normalizedTangent")[0])
                    normal = self.curve.getAtParam(param, worldSpace=world, what="normal")
                    self.assertIsInstance(normal, Vector)
                    self.assertVector(normal, cmds.getAttr(node + ".normalizedNormal")[0], places=4)

    def test_closest_point_matches_nearest_point_on_curve(self):
        """最近点とパラメーターは nearestPointOnCurve と一致する。"""
        for world in (False, True):
            for target in ((3, 4, 0), (-2, 0, 0), (12, 1, 1), (5, 0, 5)):
                with self.subTest(world=world, target=target):
                    node = cmds.createNode("nearestPointOnCurve", name=self.name("npoc#"))
                    cmds.connectAttr(self.shape + (".worldSpace[0]" if world else ".local"), node + ".inputCurve")
                    cmds.setAttr(node + ".inPosition", *target)
                    point, param = self.curve.getClosestPoint(target, worldSpace=world)
                    self.assertIsInstance(point, Vector)
                    self.assertIsInstance(param, float)
                    self.assertVector(point, cmds.getAttr(node + ".result.position")[0], places=3)
                    self.assertAlmostEqual(param, cmds.getAttr(node + ".result.parameter"), places=3)
                    self.assertVector(self.curve.getAtParam(param, worldSpace=world), point)
        point, param = self.curve.getClosestPoint(om2.MPoint(3, 4, 0))
        self.assertVector(point, self.curve.getClosestPoint([3, 4, 0])[0])

    def test_length_at_param_matches_arc_length_dimension(self):
        """始点からの弧長は arcLengthDimension(ワールド空間)と一致し、終点は getLength。"""
        for param in (0.5, 1.0, 1.5):
            with self.subTest(param=param):
                node = cmds.arcLengthDimension(self.shape + f".u[{param}]")
                node = cmds.rename(cmds.listRelatives(node, parent=True)[0], self.name("arc#"))
                self.assertAlmostEqual(self.curve.getLength(param, worldSpace=True), cmds.getAttr(node + ".arcLength"), places=4)
        end = self.curve.getParamRange()[1]
        self.assertEqual(self.curve.getLength(0.0), 0.0)
        self.assertAlmostEqual(self.curve.getLength(end), self.curve.getLength(), places=4)
        self.assertAlmostEqual(self.curve.getLength(end, True), self.curve.getLength(worldSpace=True), places=4)
        self.assertAlmostEqual(self.curve.getLength(1.0, unit="mm"), self.curve.getLength(1.0) * 10, places=6)

    def test_param_at_length_round_trip(self):
        """弧長→パラメーター→弧長が往復し、両端は範囲の端。"""
        for world in (False, True):
            total = self.curve.getLength(worldSpace=world)
            start, end = self.curve.getParamRange()
            with self.subTest(world=world):
                self.assertEqual(self.curve.getParam(length=0.0, worldSpace=world), start)
                self.assertEqual(self.curve.getParam(length=total, worldSpace=world), end)
                for ratio in (0.1, 0.5, 0.9):
                    param = self.curve.getParam(length=total * ratio, worldSpace=world)
                    self.assertAlmostEqual(self.curve.getLength(param, world), total * ratio, places=3)
        param = self.curve.getParam(length=10.0, unit="mm")
        self.assertAlmostEqual(param, self.curve.getParam(length=1.0), places=6)

    def test_params_along_open_and_closed(self):
        """開いたカーブは両端を含む等間隔、閉じたカーブは終点を含めない count 個。"""
        params = self.curve.getParamsAlong(5, worldSpace=True)
        self.assertEqual(len(params), 5)
        self.assertEqual((params[0], params[-1]), self.curve.getParamRange())
        total = self.curve.getLength(worldSpace=True)
        for index, param in enumerate(params):
            self.assertAlmostEqual(self.curve.getLength(param, True), total * index / 4, places=3)
        self.assertEqual(self.curve.getParamsAlong(1), [0.0])
        circle = self.circle.getParamsAlong(4)
        self.assertEqual(len(circle), 4)
        for index, param in enumerate(circle):
            self.assertAlmostEqual(param, index * 2.0, places=3)

    def test_no_nodes_or_undo(self):
        """照会はノードを作らず、Undo キューに積まない。"""
        cmds.flushUndo()
        before = set(cmds.ls())
        self.curve.getClosestPoint((1, 1, 1), True)
        self.curve.getAtParam(1.0, True, what="normal")
        self.curve.getParam(length=1.0, worldSpace=True)
        self.curve.getMatricesAlong(4, worldSpace=True)
        self.curve.getMatricesAlong(4, up=(0, 0, 1))
        self.assertEqual(set(cmds.ls()), before)
        self.assertFalse(cmds.undoInfo(query=True, undoName=True))

    def test_invalid_inputs(self):
        """範囲外は ValueError、型違いは TypeError。"""
        end = self.curve.getParamRange()[1]
        total = self.curve.getLength()
        cases = [
            (ValueError, self.curve.getAtParam, (end + 0.1,), {}),
            (ValueError, self.curve.getAtParam, (-0.1,), {"what": "tangent"}),
            (ValueError, self.curve.getLength, (float("nan"),), {}),
            (TypeError, self.curve.getAtParam, ("1",), {}),
            (TypeError, self.curve.getAtParam, (True,), {}),
            (TypeError, self.curve.getAtParam, (0.5,), {"worldSpace": 1}),
            (ValueError, self.curve.getParam, (), {"length": total + 0.1}),
            (ValueError, self.curve.getParam, (), {"length": -0.1}),
            (TypeError, self.curve.getParam, (), {"length": "1"}),
            (TypeError, self.curve.getClosestPoint, ("abc",), {}),
            (ValueError, self.curve.getClosestPoint, ((1, 2),), {}),
            (TypeError, self.curve.getParamsAlong, (True,), {}),
            (TypeError, self.curve.getParamsAlong, (2.0,), {}),
            (ValueError, self.curve.getParamsAlong, (0,), {}),
            (TypeError, self.curve.getMatricesAlong, (3,), {"aimAxis": 0}),
            (ValueError, self.curve.getMatricesAlong, (3,), {"aimAxis": "w"}),
            (ValueError, self.curve.getMatricesAlong, (3,), {"aimAxis": "y", "upAxis": "-y"}),
            (ValueError, self.curve.getMatricesAlong, (3, (0, 0, 0)), {}),
            (TypeError, self.curve.getMatricesAlong, (3, "up"), {}),
        ]
        for error, method, args, kwargs in cases:
            with self.subTest(method=method.__name__, args=args, kwargs=kwargs):
                self.assertRaises(error, method, *args, **kwargs)

    def test_merged_arguments_reject_invalid_combinations(self):
        """getLength・getParam・getAtParam は、同時に指定できない引数を TypeError、種類の名前の違いを ValueError にする。"""
        point = tuple(self.curve.getAtParam(1.0))[:3]
        cases = [
            ("length param+tolerance", TypeError, self.curve.getLength, (1.0,), {"tolerance": 1e-3}),
            ("param none", TypeError, self.curve.getParam, (), {}),
            ("param length=None", TypeError, self.curve.getParam, (), {"length": None}),
            ("param point+length", TypeError, self.curve.getParam, (), {"point": point, "length": 1.0}),
            ("param length+tolerance", TypeError, self.curve.getParam, (), {"length": 1.0, "tolerance": 1e-3}),
            ("param point+unit", TypeError, self.curve.getParam, (), {"point": point, "unit": "mm"}),
            ("param positional", TypeError, self.curve.getParam, (point,), {}),
            ("atParam unknown what", ValueError, self.curve.getAtParam, (1.0,), {"what": "binormal"}),
            ("atParam what type", TypeError, self.curve.getAtParam, (1.0,), {"what": 1}),
            ("atParam point+secondOrder", TypeError, self.curve.getAtParam, (1.0,), {"secondOrder": True}),
            ("atParam tangent+secondOrder", TypeError, self.curve.getAtParam, (1.0,), {"what": "tangent", "secondOrder": True}),
            ("atParam normal+secondOrder", TypeError, self.curve.getAtParam, (1.0,), {"what": "normal", "secondOrder": True}),
        ]
        for label, error, method, args, kwargs in cases:
            with self.subTest(label=label):
                with self.assertRaises(error):
                    method(*args, **kwargs)
        # 指定できる組み合わせは、今までどおりの値を返す。
        self.assertAlmostEqual(self.curve.getParam(point=point, tolerance=1e-4), 1.0, places=6)
        self.assertAlmostEqual(self.curve.getLength(tolerance=1e-3), self.curve.getLength(), places=2)
        self.assertEqual(len(self.curve.getAtParam(1.0, what="derivatives", secondOrder=True)), 3)
        self.assertVector(self.curve.getAtParam(1.0, what="point"), self.curve.getAtParam(1.0))

    def test_normal_undefined_on_straight_curve(self):
        """直線は次数1・3とも ValueError。"""
        for degree, points in ((1, [(0, 0, 0), (1, 1, 1), (3, 3, 3)]), (3, [(0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0)])):
            with self.subTest(degree=degree):
                transform = cmds.curve(name=self.name("line#"), degree=degree, point=points)
                curve = mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])
                self.assertRaises(ValueError, curve.getAtParam, 0.5, what="normal")
                self.assertVector(curve.getAtParam(0.5, what="tangent"), Vector(points[-1]).normal())
        transform = cmds.curve(name=self.name("poly#"), degree=1, point=[(0, 0, 0), (1, 0, 0), (1, 0, 1)])
        curve = mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])
        self.assertAlmostEqual(curve.getAtParam(0.5, what="normal").length(), 1.0, places=9)


class MatricesAlongTest(_CurveCase):
    def check_frames(self, curve, matrices, params, world, aim_index=0, aim_sign=1.0):
        for matrix, param in zip(matrices, params):
            self.assertIsInstance(matrix, Matrix)
            rows = [_row(matrix, index) for index in range(3)]
            for index in range(3):
                self.assertAlmostEqual(_dot(rows[index], rows[index]), 1.0, places=9)
                self.assertAlmostEqual(_dot(rows[index], rows[(index + 1) % 3]), 0.0, places=9)
            self.assertAlmostEqual(matrix.det3x3(), 1.0, places=9)
            self.assertVector(_row(matrix, 3), curve.getAtParam(param, world))
            self.assertVector([value * aim_sign for value in rows[aim_index]], curve.getAtParam(param, world, what="tangent"))

    def test_parallel_transport_on_planar_circle(self):
        """XZ 平面の円は最初の上方向が Y で、平行移動しても全点で Y のまま。"""
        matrices = self.circle.getMatricesAlong(8)
        self.assertEqual(len(matrices), 8)
        self.check_frames(self.circle, matrices, self.circle.getParamsAlong(8), False)
        for matrix in matrices:
            self.assertVector(_row(matrix, 1), (0, 1, 0))

    def test_parallel_transport_has_no_twist(self):
        """平行移動の上方向は隣の点で接線の回りに回らない(count に依らない)。"""
        for world in (False, True):
            with self.subTest(world=world):
                matrices = self.curve.getMatricesAlong(40, worldSpace=world)
                self.check_frames(self.curve, matrices, self.curve.getParamsAlong(40, world), world)
                coarse = self.curve.getMatricesAlong(3, worldSpace=world)
                self.assertVector(_row(coarse[-1], 1), _row(matrices[-1], 1), places=2)
                for previous, current in zip(matrices, matrices[1:]):
                    # 隣の上方向の、現在の接線回りの回転成分(側方軸への成分)は小さい。
                    twist = _dot(_row(previous, 1), _row(current, 2))
                    self.assertLess(abs(twist), 0.05)

    def test_up_vector_and_axes(self):
        """up を指定すると upAxis が up に最も近い向きになり、軸の符号・組み合わせを選べる。"""
        up = (0, 0, 1)
        params = self.curve.getParamsAlong(6)
        for aim, upAxis in (("x", "y"), ("-x", "z"), ("y", "-z"), ("z", "x")):
            with self.subTest(aim=aim, up=upAxis):
                matrices = self.curve.getMatricesAlong(6, up, aimAxis=aim, upAxis=upAxis)
                aim_index = "xyz".index(aim[-1])
                aim_sign = -1.0 if aim.startswith("-") else 1.0
                up_index = "xyz".index(upAxis[-1])
                up_sign = -1.0 if upAxis.startswith("-") else 1.0
                self.check_frames(self.curve, matrices, params, False, aim_index, aim_sign)
                for matrix, param in zip(matrices, params):
                    tangent = self.curve.getAtParam(param, what="tangent")
                    expected = Vector(up) - tangent * _dot(up, tangent)
                    expected.normalize()
                    self.assertVector([value * up_sign for value in _row(matrix, up_index)], expected)

    def test_up_parallel_to_tangent_uses_previous(self):
        """接線と平行な点は直前の向き、先頭が平行なら最初に決まった向きを使う。"""
        transform = cmds.curve(name=self.name("bend#"), degree=1, point=[(0, 0, 0), (0, 2, 0), (2, 2, 0)])
        curve = mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])
        matrices = curve.getMatricesAlong(5, up=(0, 1, 0))
        self.assertVector(_row(matrices[0], 1), _row(matrices[2], 1))
        self.assertVector(_row(matrices[2], 1), (0, 1, 0))
        line = cmds.curve(name=self.name("line#"), degree=1, point=[(0, 0, 0), (0, 2, 0)])
        line = mlib.getNode(cmds.listRelatives(line, shapes=True, fullPath=True)[0])
        self.assertRaises(ValueError, line.getMatricesAlong, 3, (0, 1, 0))
        self.assertEqual(len(line.getMatricesAlong(3)), 3)

    def test_normal_rejects_nearly_straight_degree_one_curve(self):
        """次数1で、許容誤差の中で一直線のカーブ(端から測ってずれが長さの1e-9倍以下)は法線がValueError。"""
        transform = cmds.curve(name=self.name("nearLine"), degree=1, point=[(0, 0, 0), (1, 0, 0), (2, 2e-9, 0)])
        shape = mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])
        for param in (0.5, 1.5):
            with self.subTest(param=param), self.assertRaises(ValueError):
                shape.getAtParam(param, what="normal")


if __name__ == "__main__":
    unittest.main()
