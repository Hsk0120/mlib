"""``curveFit`` を Maya なしで確認する。

- mlib.common の CurveFit・DampedSpring の約束を、Mayaなしで固定する仕様テスト(担当D)。
"""

import copy
import importlib.util
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load(relative, name):
    """mlib のソースファイルを単独のモジュールとして読み込む。

    Args:
        relative (str): mlib からの相対パス。
        name (str): 読み込むモジュール名。

    Returns:
        module: 読み込んだモジュール。
    """
    spec = importlib.util.spec_from_file_location(name, str(ROOT / relative))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CurveFit = _load("common/curveFit.py", "mlib_spec_d_curvefit").CurveFit


DampedSpring = _load("common/dampedSpring.py", "mlib_spec_d_dampedspring").DampedSpring


def _evaluate(controls, parameter):
    """基底重みでCVを重み付けした点を返す。

    Args:
        controls (list[list[float]]): CV座標。
        parameter (float): 0〜1のパラメータ。

    Returns:
        list[float]: 評価した3次元点。
    """
    weights = CurveFit.basis(len(controls), parameter)
    return [sum(w * c[axis] for w, c in zip(weights, controls)) for axis in range(3)]


class CurveFitBasisSpecTest(unittest.TestCase):
    """CurveFit.basis の範囲検査・端点・1の分割を固定する。"""

    def test_rejects_count_below_four_and_parameter_out_of_range(self):
        """countが4未満、parameterが0〜1の外ならValueError。"""
        for count, parameter in ((3, 0.5), (0, 0.0), (4, -1e-9), (4, 1.0 + 1e-9), (8, 2.0)):
            with self.assertRaises(ValueError):
                CurveFit.basis(count, parameter)

    def test_length_matches_count_and_values_are_float(self):
        """重みはCV数と同じ長さのfloatのlist。"""
        for count in (4, 5, 7, 12, 32):
            for parameter in (0.0, 0.13, 0.5, 0.99, 1.0):
                weights = CurveFit.basis(count, parameter)
                self.assertIsInstance(weights, list)
                self.assertEqual(len(weights), count)
                self.assertTrue(all(isinstance(w, float) for w in weights))

    def test_partition_of_unity_and_non_negative(self):
        """全パラメータで重みの和は1、各重みは0以上。"""
        for count in (4, 6, 9):
            for step in range(101):
                weights = CurveFit.basis(count, step / 100.0)
                self.assertAlmostEqual(sum(weights), 1.0, places=12)
                self.assertTrue(all(w >= -1e-15 for w in weights))

    def test_clamped_end_points(self):
        """clamped knotのため、0は先頭CV、1は末尾CVだけの重みになる。"""
        self.assertEqual(CurveFit.basis(6, 0.0), [1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        self.assertEqual(CurveFit.basis(6, 1), [0.0, 0.0, 0.0, 0.0, 0.0, 1.0])
        # int の 0 も受け付ける。
        self.assertEqual(CurveFit.basis(4, 0)[0], 1.0)

    def test_four_controls_are_bernstein_polynomials(self):
        """CV数4(1スパン)では3次のBernstein基底と一致する。"""
        for step in range(11):
            t = step / 10.0
            expected = [(1 - t) ** 3, 3 * t * (1 - t) ** 2, 3 * t * t * (1 - t), t**3]
            for actual, wanted in zip(CurveFit.basis(4, t), expected):
                self.assertAlmostEqual(actual, wanted, places=12)

    def test_local_support(self):
        """各パラメータで0でない重みは連続する高々4個(3次のため)。"""
        for step in range(1, 100):
            weights = CurveFit.basis(10, step / 100.0)
            nonzero = [i for i, w in enumerate(weights) if abs(w) > 1e-15]
            self.assertLessEqual(len(nonzero), 4)
            self.assertEqual(nonzero, list(range(nonzero[0], nonzero[-1] + 1)))


class CurveFitFitSpecTest(unittest.TestCase):
    """CurveFit.fit の入力検証・端点・直線の再現を固定する。"""

    def test_rejects_invalid_count(self):
        """countは4〜32のint。boolやfloatもValueError。"""
        points = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
        for count in (3, 33, 4.0, True, "4", None):
            with self.assertRaises(ValueError):
                CurveFit.fit(points, count)

    def test_rejects_too_few_points(self):
        """点が2個未満ならValueError。"""
        with self.assertRaises(ValueError):
            CurveFit.fit([(0.0, 0.0, 0.0)], 4)
        with self.assertRaises(ValueError):
            CurveFit.fit([], 4)

    def test_rejects_non_3d_and_non_finite_points(self):
        """3成分以外・NaN・無限大はValueError。"""
        for bad in ([(0, 0), (1, 1)], [(0, 0, 0, 0), (1, 0, 0, 0)], [(0, 0, 0), (float("nan"), 0, 0)], [(0, 0, 0), (float("inf"), 0, 0)]):
            with self.assertRaises(ValueError):
                CurveFit.fit(bad, 4)

    def test_rejects_zero_length_chain(self):
        """全点が同じ位置なら長さ0としてValueError。"""
        with self.assertRaises(ValueError):
            CurveFit.fit([(1.0, 2.0, 3.0)] * 5, 4)

    def test_result_shape_and_exact_end_points(self):
        """CV数ぶんの3成分listを返し、両端CVは入力の両端と完全に一致する独立したlist。"""
        points = [(math.cos(i * 0.3), math.sin(i * 0.3), i * 0.1) for i in range(12)]
        original = copy.deepcopy(points)
        result = CurveFit.fit(points, 7)
        self.assertEqual(len(result), 7)
        self.assertTrue(all(isinstance(row, list) and len(row) == 3 for row in result))
        self.assertEqual(result[0], list(points[0]))
        self.assertEqual(result[-1], list(points[-1]))
        self.assertIsNot(result[0], points[0])
        self.assertEqual(points, original)
        self.assertTrue(all(math.isfinite(v) for row in result for v in row))

    def test_two_points_regularize_to_straight_line(self):
        """2点だけでも、両端の直線上へ等間隔に近いCVを返す。"""
        result = CurveFit.fit([(0.0, 0.0, 0.0), (9.0, 0.0, 0.0)], 4)
        for row in result:
            self.assertAlmostEqual(row[1], 0.0, places=6)
            self.assertAlmostEqual(row[2], 0.0, places=6)
        xs = [row[0] for row in result]
        self.assertEqual(xs, sorted(xs))

    def test_reproduces_uniform_straight_line(self):
        """等間隔の直線上の点は、フィットしたカーブ上で同じ位置に再現される。"""
        points = [(i * 0.5, i * 0.25, -i * 0.1) for i in range(21)]
        controls = CurveFit.fit(points, 6)
        total = math.sqrt(10.0**2 + 5.0**2 + 2.0**2)
        for _index, point in enumerate(points):
            length = math.sqrt(sum(v * v for v in point))
            evaluated = _evaluate(controls, length / total)
            for axis in range(3):
                self.assertAlmostEqual(evaluated[axis], point[axis], places=4)

    def test_deterministic(self):
        """同じ入力には同じ結果を返す。"""
        points = [(i, math.sin(i), 0.0) for i in range(8)]
        self.assertEqual(CurveFit.fit(points, 5), CurveFit.fit(points, 5))


if __name__ == "__main__":
    unittest.main()
