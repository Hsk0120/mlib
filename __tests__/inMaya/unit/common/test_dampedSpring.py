"""``mlib.common.dampedSpring`` のテスト。

- 減衰のあるばねの計算結果の性質(先頭の位置・追従・減衰・上限・成分ごとの独立)と入力の検査を確かめる。
"""

import math
import sys
import unittest

import mlib

mlib.reload()

from mlib.common import DampedSpring

_STEP = 1.0 / 24.0


class DampedSpringTest(unittest.TestCase):
    """DampedSpring.solveの結果の性質と、不正な入力の例外を確かめる。"""

    def test_first_row_and_length(self):
        """結果はサンプルと同じ数で、先頭は先頭の目標そのもの。"""
        samples = [(1.0, 2.0), (3.0, 4.0), (5.0, 6.0)]
        result = DampedSpring.solve(samples, _STEP)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], (1.0, 2.0))
        self.assertTrue(all(isinstance(row, tuple) and len(row) == 2 for row in result))
        self.assertEqual(DampedSpring.solve([(7.0,)], _STEP), [(7.0,)])

    def test_constant_target_stays(self):
        """目標が動かなければ、位置も動かない。"""
        result = DampedSpring.solve([(2.5, -1.0)] * 10, _STEP)
        for row in result:
            self.assertEqual(row, (2.5, -1.0))

    def test_step_response_converges_and_is_deterministic(self):
        """段差の目標へ近づき、同じ入力なら毎回同じ結果になる。"""
        samples = [(0.0,)] + [(10.0,)] * 72
        first = DampedSpring.solve(samples, _STEP, frequency=3.0, damping=1.0, limit=100.0)
        second = DampedSpring.solve(samples, _STEP, frequency=3.0, damping=1.0, limit=100.0)
        self.assertEqual(first, second)
        self.assertLess(first[1][0], 10.0)
        self.assertAlmostEqual(first[-1][0], 10.0, places=3)

    def test_damping_controls_overshoot(self):
        """減衰が小さいと目標を行き過ぎ、臨界減衰(1)では行き過ぎない。"""
        samples = [(0.0,)] + [(10.0,)] * 48
        under = DampedSpring.solve(samples, _STEP, frequency=2.0, damping=0.1, limit=100.0)
        critical = DampedSpring.solve(samples, _STEP, frequency=2.0, damping=1.0, limit=100.0)
        self.assertGreater(max(row[0] for row in under), 10.0)
        self.assertLessEqual(max(row[0] for row in critical), 10.0 + 1e-9)

    def test_limit_bounds_distance_from_goal(self):
        """目標から離れる量はlimitを超えない。"""
        samples = [(float(i * 10),) for i in range(12)]
        limit = 0.5
        result = DampedSpring.solve(samples, _STEP, frequency=1.0, damping=0.5, limit=limit)
        for row, goal in zip(result, samples):
            self.assertLessEqual(abs(row[0] - goal[0]), limit + 1e-9)

    def test_components_are_independent(self):
        """成分ごとに別々に計算した結果と、まとめて計算した結果は同じ。"""
        xs = [0.0, 3.0, -2.0, 5.0, 5.0, 1.0]
        ys = [1.0, 1.0, 4.0, -3.0, 0.0, 2.0]
        together = DampedSpring.solve(list(zip(xs, ys)), _STEP, frequency=4.0, damping=0.3, limit=2.0)
        alone_x = DampedSpring.solve([(x,) for x in xs], _STEP, frequency=4.0, damping=0.3, limit=2.0)
        alone_y = DampedSpring.solve([(y,) for y in ys], _STEP, frequency=4.0, damping=0.3, limit=2.0)
        self.assertEqual([row[0] for row in together], [row[0] for row in alone_x])
        self.assertEqual([row[1] for row in together], [row[0] for row in alone_y])

    def test_accepts_numbers_as_text_and_ints(self):
        """サンプルはfloat()で数値にする(intや数値の文字列も受け付ける)。"""
        self.assertEqual(DampedSpring.solve([(1, "2")], 1), [(1.0, 2.0)])

    def test_invalid_samples(self):
        """空・長さ違い・成分なし・有限でないサンプルはValueError。"""
        cases = [[], [()], [(1.0,), (1.0, 2.0)], [(math.nan,)], [(1.0,), (math.inf,)], [("a",)]]
        for samples in cases:
            with self.subTest(samples=samples), self.assertRaises(ValueError):
                DampedSpring.solve(samples, _STEP)

    def test_invalid_settings(self):
        """設定が有限でない・範囲外・内部の刻みが多すぎる場合はValueError。"""
        samples = [(0.0,), (1.0,)]
        cases = [
            {"secondsPerSample": math.nan},
            {"secondsPerSample": 0.0},
            {"secondsPerSample": -1.0},
            {"secondsPerSample": _STEP, "frequency": 0.0},
            {"secondsPerSample": _STEP, "frequency": 30.5},
            {"secondsPerSample": _STEP, "frequency": math.inf},
            {"secondsPerSample": _STEP, "damping": -0.1},
            {"secondsPerSample": _STEP, "damping": 2.1},
            {"secondsPerSample": _STEP, "limit": 0.0},
            {"secondsPerSample": _STEP, "limit": math.nan},
            {"secondsPerSample": 100.0, "frequency": 30.0},
        ]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                DampedSpring.solve(samples, **kwargs)

    def test_boundary_settings_are_accepted(self):
        """範囲の端(frequency=30・damping=0と2)は受け付ける。"""
        samples = [(0.0,), (1.0,)]
        for kwargs in ({"frequency": 30.0}, {"damping": 0.0}, {"damping": 2.0}):
            with self.subTest(kwargs=kwargs):
                self.assertEqual(len(DampedSpring.solve(samples, _STEP, **kwargs)), 2)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
