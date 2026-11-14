"""``dampedSpring`` を Maya なしで確認する。

- mlib.common の CurveFit・DampedSpring の約束を、Mayaなしで固定する仕様テスト(担当D)。
"""

import copy
import importlib.util
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


class DampedSpringSpecTest(unittest.TestCase):
    """DampedSpring.solve の入力検証・初期条件・減衰・制限を固定する。"""

    def test_result_shape_and_initial_value(self):
        """入力と同数のtupleを返し、先頭は先頭目標そのもの。"""
        samples = [(0, 1), (1, 1), (2, 1)]
        result = DampedSpring.solve(samples, 1 / 24.0)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)
        self.assertTrue(all(isinstance(row, tuple) and len(row) == 2 for row in result))
        self.assertEqual(result[0], (0.0, 1.0))
        self.assertTrue(all(isinstance(v, float) for v in result[0]))

    def test_single_sample_returns_itself(self):
        """1サンプルでは計算せず先頭目標だけを返す。"""
        self.assertEqual(DampedSpring.solve([(3, 4, 5)], 0.1), [(3.0, 4.0, 5.0)])

    def test_constant_target_stays_constant(self):
        """初速ゼロなので、目標が一定なら値は変わらない。"""
        result = DampedSpring.solve([(2.5,)] * 20, 1 / 30.0)
        self.assertEqual(result, [(2.5,)] * 20)

    def test_axes_are_independent(self):
        """各成分は独立して計算する。一定の成分は他の成分の動きに影響されない。"""
        samples = [(0.0 if i == 0 else 1.0, 7.0) for i in range(30)]
        result = DampedSpring.solve(samples, 1 / 24.0)
        self.assertTrue(all(row[1] == 7.0 for row in result))
        alone = DampedSpring.solve([(row[0],) for row in samples], 1 / 24.0)
        self.assertEqual([row[0] for row in result], [row[0] for row in alone])

    def test_underdamped_overshoots_and_critical_converges(self):
        """減衰比0.1は目標を超え、減衰比1はほぼ超えずに目標へ収束する。"""
        samples = [(0.0,)] + [(1.0,)] * 120
        under = [row[0] for row in DampedSpring.solve(samples, 1 / 24.0, frequency=2.0, damping=0.1)]
        self.assertGreater(max(under), 1.2)
        critical = [row[0] for row in DampedSpring.solve(samples, 1 / 24.0, frequency=2.0, damping=1.0)]
        self.assertLess(max(critical), 1.0 + 1e-3)
        self.assertAlmostEqual(critical[-1], 1.0, places=3)

    def test_zero_damping_keeps_oscillating(self):
        """減衰比0では収束せず振動を続ける。"""
        samples = [(0.0,)] + [(1.0,)] * 200
        values = [row[0] for row in DampedSpring.solve(samples, 1 / 24.0, frequency=1.0, damping=0.0)]
        tail = values[100:]
        self.assertGreater(max(tail) - min(tail), 1.0)

    def test_limit_bounds_the_lag(self):
        """各サンプル時点で目標との差はlimit以内に収まる。"""
        samples = [(0.0,)] + [(10.0,)] * 10
        result = DampedSpring.solve(samples, 1 / 24.0, frequency=0.5, damping=1.0, limit=0.25)
        for target, row in zip(samples, result):
            self.assertLessEqual(abs(row[0] - target[0]), 0.25 + 1e-12)

    def test_rejects_invalid_samples(self):
        """空・空行・長さ不揃い・非有限の目標はValueError。"""
        for samples in ([], [()], [(0, 0), (1,)], [(0,), (float("nan"),)], [(0,), (float("inf"),)]):
            with self.assertRaises(ValueError):
                DampedSpring.solve(samples, 0.04)

    def test_rejects_invalid_settings(self):
        """間隔・振動数・減衰比・制限が範囲外または非有限ならValueError。"""
        cases = [
            dict(secondsPerSample=0.0),
            dict(secondsPerSample=-1.0),
            dict(secondsPerSample=float("nan")),
            dict(frequency=0.0),
            dict(frequency=30.0001),
            dict(damping=-0.01),
            dict(damping=2.01),
            dict(limit=0.0),
            dict(limit=float("inf")),
        ]
        for overrides in cases:
            options = dict(secondsPerSample=0.04)
            options.update(overrides)
            with self.assertRaises(ValueError, msg=repr(overrides)):
                DampedSpring.solve([(0.0,), (1.0,)], **options)

    def test_boundary_settings_are_accepted(self):
        """振動数30・減衰比0と2は範囲内として受け付ける。"""
        DampedSpring.solve([(0.0,), (1.0,)], 0.04, frequency=30.0)
        DampedSpring.solve([(0.0,), (1.0,)], 0.04, damping=0.0)
        DampedSpring.solve([(0.0,), (1.0,)], 0.04, damping=2.0)

    def test_rejects_too_large_interval(self):
        """内部刻みが10000を超える間隔はValueError。"""
        with self.assertRaises(ValueError):
            DampedSpring.solve([(0.0,), (1.0,)], 3.0, frequency=30.0)

    def test_deterministic_and_input_not_modified(self):
        """同じ入力には同じ結果を返し、入力の列は変更しない。"""
        samples = [[0.0, 1.0], [0.5, 0.0], [2.0, -1.0]]
        before = copy.deepcopy(samples)
        first = DampedSpring.solve(samples, 1 / 24.0)
        self.assertEqual(first, DampedSpring.solve(samples, 1 / 24.0))
        self.assertEqual(samples, before)


if __name__ == "__main__":
    unittest.main()
