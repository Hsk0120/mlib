"""``mlib.common.curveFit`` のテスト。

- mlib.common の公開APIの約束を固定する仕様テスト(担当D)。
"""

import sys
import unittest
import uuid

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.common import CurveFit


def _maya_year():
    """現在のMayaの年版を cmds から独立に求める。

    Returns:
        int: 2027などの年版。
    """
    return int(str(cmds.about(version=True)).split(".")[0])


class CurveFitMayaSpecTest(unittest.TestCase):
    """CurveFit.basisがMayaの3次clamped一様ノットのNURBS評価と一致することを確かめる。"""

    def setUp(self):
        """作成したノードを記録する一時名前空間を作る。"""
        self.ns = "mlibSpecDCurve_" + uuid.uuid4().hex[:8]
        cmds.namespace(add=self.ns)

    def tearDown(self):
        """一時名前空間を中身ごと削除する。"""
        cmds.namespace(removeNamespace=self.ns, deleteNamespaceContent=True)

    def test_basis_matches_maya_curve_evaluation(self):
        """CVを基底重みで混ぜた点は、MFnNurbsCurve.getPointAtParamと一致する。"""
        controls = [(0, 0, 0), (1, 2, 0), (3, -1, 1), (4, 3, 2), (6, 0, -1), (7, 1, 0), (9, 2, 3)]
        fn = self._maya_curve(controls)
        self.assertAlmostEqual(fn.knotDomain[0], 0.0)
        self.assertAlmostEqual(fn.knotDomain[1], 1.0)
        for step in range(21):
            parameter = step / 20.0
            weights = CurveFit.basis(len(controls), parameter)
            point = fn.getPointAtParam(parameter, om2.MSpace.kObject)
            for axis in range(3):
                mixed = sum(w * c[axis] for w, c in zip(weights, controls))
                self.assertAlmostEqual(mixed, point[axis], places=6, msg=(parameter, axis))

    def test_fit_controls_reproduce_samples_on_maya_curve(self):
        """fitしたCVでMayaカーブを作ると、直線上の等間隔サンプルを通る。"""
        points = [(i * 1.0, i * 0.5, 0.0) for i in range(16)]
        controls = CurveFit.fit(points, 5)
        fn = self._maya_curve([tuple(row) for row in controls])
        for point in points:
            closest = fn.closestPoint(om2.MPoint(*point), space=om2.MSpace.kObject)[0]
            self.assertLess(closest.distanceTo(om2.MPoint(*point)), 1e-4)

    def test_basis_end_and_partition_of_unity(self):
        """parameter=1は最後のCVだけが1で、どのparameterでもウェイトの合計は1。"""
        self.assertEqual(CurveFit.basis(5, 1.0), [0.0, 0.0, 0.0, 0.0, 1.0])
        for parameter in (0.0, 0.25, 0.5, 0.99):
            with self.subTest(parameter=parameter):
                weights = CurveFit.basis(6, parameter)
                self.assertEqual(len(weights), 6)
                self.assertAlmostEqual(sum(weights), 1.0)

    def test_fit_returns_count_controls_in_same_space(self):
        """fitはcount個の3次元のCVを返し、両端のCVは端の点に一致する。"""
        points = [(0.0, 0.0, 0.0), (2.0, 1.0, 0.0), (4.0, 0.0, 1.0)]
        controls = CurveFit.fit(points, 4)
        self.assertEqual(len(controls), 4)
        self.assertTrue(all(len(row) == 3 for row in controls))
        for axis in range(3):
            self.assertAlmostEqual(controls[0][axis], points[0][axis], places=4)
            self.assertAlmostEqual(controls[-1][axis], points[-1][axis], places=4)

    def test_few_points_place_controls_evenly_on_the_line(self):
        """点がCVより少なく決まらないCVは、端の点を結ぶ直線上へ等間隔に並ぶ(正則化の寄せ先)。"""
        start, end = (1.0, -2.0, 3.0), (11.0, 3.0, -2.0)
        for count in (5, 8):
            with self.subTest(count=count):
                controls = CurveFit.fit([start, end], count)
                for index, control in enumerate(controls):
                    expected = [a + (b - a) * index / (count - 1) for a, b in zip(start, end)]
                    for axis in range(3):
                        self.assertAlmostEqual(control[axis], expected[axis], places=3)

    def test_invalid_input(self):
        """countやparameterの範囲外、点の不足・次元違い・有限でない値・長さ0の並びはValueError。"""
        for count, parameter in ((3, 0.5), (4, -0.1), (4, 1.1)):
            with self.subTest(count=count, parameter=parameter), self.assertRaises(ValueError):
                CurveFit.basis(count, parameter)
        line = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
        cases = [
            (line, 3),
            (line, 33),
            (line, 4.0),
            (line, True),
            ([(0.0, 0.0, 0.0)], 4),
            ([(0.0, 0.0), (1.0, 0.0)], 4),
            ([(0.0, 0.0, 0.0), (float("nan"), 0.0, 0.0)], 4),
            ([(1.0, 2.0, 3.0)] * 3, 4),
        ]
        for points, count in cases:
            with self.subTest(points=points, count=count), self.assertRaises(ValueError):
                CurveFit.fit(points, count)

    def _maya_curve(self, controls):
        """同じノット列を持つMayaの3次カーブを作り、関数セットを返す。"""
        count = len(controls)
        spans = count - 3
        knots = [0.0] * 3 + [i / float(spans) for i in range(1, spans)] + [1.0] * 3
        name = cmds.curve(degree=3, point=controls, knot=knots, name=self.ns + ":curve")
        shape = cmds.listRelatives(name, shapes=True, fullPath=True)[0]
        return om2.MFnNurbsCurve(om2.MSelectionList().add(shape).getDagPath(0))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
