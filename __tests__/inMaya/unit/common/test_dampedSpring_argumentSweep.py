"""DampedSpring.solve の引数を、表から網羅して確かめる(段1〜3)。

結果は docstring に書いた性質(最初は先頭の目標・目標との差は limit 以下・成分の数がそろう)と、
同じ半陰的 Euler 法をテストの中で計算した値と突き合わせる。シーンを変えない。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import inspect
import sys
import unittest

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Method

from mlib.common.dampedSpring import DampedSpring


def _host(owner, **functions):
    """静的メソッドを、表の対象のメソッドとして呼べるようにする(部品は対象の型からメソッドを読むため)。"""

    def wrap(function):
        def method(self, *args, **kwargs):
            return function(*args, **kwargs)

        signature = inspect.signature(function)
        first = inspect.Parameter("self", inspect.Parameter.POSITIONAL_ONLY)
        method.__signature__ = signature.replace(parameters=[first, *signature.parameters.values()])
        method.__doc__ = function.__doc__
        return method

    return type(owner, (), {name: wrap(function) for name, function in functions.items()})()


def _expect_solve(case, call):
    kwargs = call.kwargs
    samples = [tuple(float(value) for value in sample) for sample in kwargs["samples"]]
    limit = kwargs.get("limit", 45.0)
    case.assertEqual(len(call.result), len(samples))
    case.assertSequenceAlmostEqual(call.result[0], samples[0])
    for result, target in zip(call.result, samples):
        case.assertEqual(len(result), len(target))
        for value, goal in zip(result, target):
            case.assertLessEqual(abs(value - goal), limit + 1e-9)
    if all(sample == samples[0] for sample in samples):
        for result in call.result:
            case.assertSequenceAlmostEqual(result, samples[0])


STEP = [(0.0,)] * 2 + [(10.0,)] * 10
SAMPLES = (STEP, [(0.0, 0.0, 0.0), (1.0, 2.0, 3.0), (2.0, 4.0, 6.0)], [(5.0, -5.0)] * 4, [[1, 2]], ((0.0,), (100.0,), (100.0,)))

METHODS = (
    Method(
        "solve",
        lambda case: _host("DampedSpring", solve=DampedSpring.solve),
        args=(STEP, 1.0 / 24.0),
        values={
            "samples": SAMPLES,
            "secondsPerSample": (1.0 / 24.0, 1.0 / 60.0, 0.5, 1),
            "frequency": (3.0, 0.1, 30.0, 1),
            "damping": (0.5, 0.0, 1.0, 2.0, 0),
            "limit": (45.0, 0.5, 1000.0, 1),
        },
        replace=("samples", "secondsPerSample", "frequency", "damping", "limit"),
        invalid={
            "samples": ([], [(0.0,), (0.0, 1.0)], [(float("nan"),)], None, 1.5, "abc"),
            "secondsPerSample": (0.0, -1.0, 1000.0, float("nan"), "a", None),
            "frequency": (0.0, -1.0, 30.5, float("inf"), "a", None),
            "damping": (-0.1, 2.1, float("nan"), "a", None),
            "limit": (0.0, -1.0, float("inf"), "a", None),
        },
        expect=_expect_solve,
        writes=False,
        known={
            "invalid:samples=None": "並びでない samples で Raises に無い TypeError",
            "invalid:samples=1.5": "並びでない samples で Raises に無い TypeError",
            **{
                f"invalid:{name}={value}": "数でない設定の値で Raises に無い TypeError"
                for name in ("secondsPerSample", "frequency", "damping", "limit")
                for value in ("'a'", "None")
            },
        },
    ),
)


class DampedSpringArgumentSweepTest(ArgumentSweepCase):
    """DampedSpring.solve の引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
