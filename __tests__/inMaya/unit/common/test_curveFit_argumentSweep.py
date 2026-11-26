"""CurveFit の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

basis のウェイトは、om2 の ``MFnNurbsCurve`` で作った同じノット(両端固定・等間隔)の3次カーブの点と突き合わせる
(CV を並べたカーブの、正規化したパラメータの点 = ウェイトで CV を足した点)。シーンを変えない。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import inspect
import math
import sys
import unittest

import maya.api.OpenMaya as om2

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Method

from mlib.common.curveFit import CurveFit


def _host(owner, **functions):
    """クラスメソッド・静的メソッドを、表の対象のメソッドとして呼べるようにする(部品は対象の型からメソッドを読むため)。"""

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
    return _host("CurveFit", basis=CurveFit.basis, fit=CurveFit.fit)


def _cvs(count):
    return [om2.MPoint(index, math.sin(index), index * index * 0.1) for index in range(count)]


def _om2_point(count, parameter):
    """両端固定・等間隔のノットの3次カーブ(om2)で、正規化したパラメータの点を求める。"""
    spans = count - 3
    knots = [0.0, 0.0] + [float(index) for index in range(spans + 1)] + [float(spans), float(spans)]
    data = om2.MFnNurbsCurveData().create()
    curve = om2.MFnNurbsCurve()
    curve.create(_cvs(count), knots, 3, om2.MFnNurbsCurve.kOpen, False, False, data)
    return curve.getPointAtParam(parameter * spans, om2.MSpace.kObject)


def _expect_basis(case, call):
    count, parameter = call.kwargs["count"], call.kwargs["parameter"]
    weights = call.result
    case.assertEqual(len(weights), count)
    case.assertAlmostEqual(sum(weights), 1.0, places=9)
    case.assertTrue(all(weight >= -1e-12 for weight in weights))
    point = om2.MPoint(0.0, 0.0, 0.0)
    for weight, cv in zip(weights, _cvs(count)):
        point += om2.MVector(cv) * weight
    expected = _om2_point(count, parameter)
    case.assertSequenceAlmostEqual([point.x, point.y, point.z], [expected.x, expected.y, expected.z], places=6)


def _expect_fit(case, call):
    """CV の数が count で、直線上の点からは直線上の CV になり、両端の CV は両端の点に近い。"""
    points, count = call.kwargs["points"], call.kwargs["count"]
    case.assertEqual(len(call.result), count)
    case.assertTrue(all(len(cv) == 3 for cv in call.result))
    first, last = om2.MVector(*points[0]), om2.MVector(*points[-1])
    if points in (LINE, LINE_TWO):
        axis = (last - first).normal()
        for cv in call.result:
            case.assertAlmostEqual(((om2.MVector(*cv) - first) ^ axis).length(), 0.0, places=6)
    case.assertSequenceAlmostEqual(call.result[0], first, places=3)
    case.assertSequenceAlmostEqual(call.result[-1], last, places=3)


LINE = ((0.0, 0.0, 0.0), (1.0, 1.0, 0.0), (2.0, 2.0, 0.0), (5.0, 5.0, 0.0))
LINE_TWO = ((0.0, 0.0, 0.0), (0.0, 0.0, 10.0))
ARC = tuple((math.cos(angle), math.sin(angle), 0.0) for angle in (0.0, 0.4, 0.8, 1.2, 1.6, 2.0, 2.4, 2.8))

METHODS = (
    Method(
        "basis",
        _functions,
        args=(4, 0.5),
        values={"count": (4, 5, 7, 12, 32), "parameter": (0.0, 0.25, 0.5, 0.999, 1.0, 0, 1)},
        replace=("count", "parameter"),
        invalid={"count": (3, 0, -1, 1.5, "a", None), "parameter": (-0.1, 1.1, float("nan"), float("inf"), "a", None)},
        expect=_expect_basis,
        writes=False,
        known={
            "invalid:count='a'": "数でない count で Raises に無い TypeError(比較の英語の文)",
            "invalid:count=None": "数でない count で Raises に無い TypeError(比較の英語の文)",
            "invalid:parameter='a'": "数でない parameter で Raises に無い TypeError(比較の英語の文)",
            "invalid:parameter=None": "数でない parameter で Raises に無い TypeError(比較の英語の文)",
        },
    ),
    Method(
        "fit",
        _functions,
        args=(LINE, 4),
        values={"points": (LINE, LINE_TWO, ARC, [om2.MPoint(0, 0, 0), om2.MVector(1, 2, 3), (4, 4, 4)], tuple(ARC)), "count": (4, 5, 8, 16, 32)},
        replace=("points", "count"),
        invalid={
            "points": ([(0.0, 0.0, 0.0)], [], [(0, 0, 0), (0, 0, 0)], [(0, 0), (1, 1)], [(0, 0, 0), (float("nan"), 0, 0)], None, 1.5, "abc"),
            "count": (3, 0, 1, -1, 33, 1.5, True, "4", None),
        },
        expect=_expect_fit,
        writes=False,
        known={"invalid:points=None": "並びでない points で Raises に無い TypeError", "invalid:points=1.5": "並びでない points で Raises に無い TypeError"},
    ),
)


class CurveFitArgumentSweepTest(ArgumentSweepCase):
    """CurveFit の公開メソッドの引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
