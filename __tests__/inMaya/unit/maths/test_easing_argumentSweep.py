"""easing.ease の引数を、表から網羅して確かめる(段1〜3)。

ease は標準ライブラリだけで計算する関数なので、om2 の同じ計算は無い。結果は docstring に書いた性質
(0〜1 に収まる・0 と 1 の外は端の値・点 (0.5, 0.5) について対称)と、``"linear"`` の値で確かめる。
シーンを変えないので、Undo・fast の性質は当てはまらない。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import fractions
import inspect
import sys
import unittest

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Method

from mlib.maths import easing


def _host(owner, **functions):
    """関数を、表の対象のメソッドとして呼べるようにする(部品は対象の型からメソッドを読むため)。"""

    def wrap(function):
        def method(self, *args, **kwargs):
            return function(*args, **kwargs)

        signature = inspect.signature(function)
        first = inspect.Parameter("self", inspect.Parameter.POSITIONAL_ONLY)
        method.__signature__ = signature.replace(parameters=[first, *signature.parameters.values()])
        method.__doc__ = function.__doc__
        return method

    return type(owner, (), {name: wrap(function) for name, function in functions.items()})()


def _functions(case):
    return _host("easing", ease=easing.ease)


def _expect_ease(case, call):
    t, curve = float(call.kwargs["t"]), call.kwargs.get("curve", "cubic")
    case.assertIsInstance(call.result, float)
    case.assertTrue(0.0 <= call.result <= 1.0)
    if t <= 0.0:
        case.assertEqual(call.result, 0.0)
    elif t >= 1.0:
        case.assertEqual(call.result, 1.0)
    else:
        case.assertAlmostEqual(call.result, 1.0 - easing.ease(1.0 - t, curve), places=9)
        if curve == "linear":
            case.assertAlmostEqual(call.result, t, places=12)


METHODS = (
    Method(
        "ease",
        _functions,
        args=(0.25,),
        values={"t": (0.0, 0.25, 0.5, 0.75, 1.0, -3.0, 2.0, 0, 1, fractions.Fraction(1, 3), float("inf"), float("-inf")), "curve": easing.CURVES},
        replace=("t", "curve"),
        invalid={"t": ("a", None, True, float("nan"), (0.5,)), "curve": (1.5, None, "Cubic", "", "__argumentSweepInvalid__")},
        expect=_expect_ease,
        writes=False,
    ),
)


class EasingArgumentSweepTest(ArgumentSweepCase):
    """easing.ease の引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
