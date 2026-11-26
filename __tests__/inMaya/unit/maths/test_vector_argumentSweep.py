"""Vectorの公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

結果は om2 の同じ計算(``om2.MVector`` の演算・``MQuaternion`` の回転)と突き合わせる。
数学型はシーンを変えないので、Undo・fast の性質は当てはまらない(表は ``writes=False`` にし、
状態は対象の値そのものにして、メソッドが自身を変えないことを確かめる)。
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

from mlib.maths import Translate, Vector


def _host(owner, **functions):
    """クラスメソッドを、表の対象のメソッドとして呼べるようにする(部品は対象の型からメソッドを読むため)。"""

    def wrap(function):
        def method(self, *args, **kwargs):
            return function(*args, **kwargs)

        signature = inspect.signature(function)
        first = inspect.Parameter("self", inspect.Parameter.POSITIONAL_ONLY)
        method.__signature__ = signature.replace(parameters=[first, *signature.parameters.values()])
        method.__doc__ = function.__doc__
        return method

    return type(owner, (), {name: wrap(function) for name, function in functions.items()})()


def _value(case, target):
    """値の状態(成分の並び)。メソッドが自身を変えないことを確かめる。"""
    return list(target) if isinstance(target, om2.MVector) else None


def _vector(case):
    return Vector(1.0, 2.0, 3.0)


def _classes(case):
    return _host("Vector", fromAxis=Vector.fromAxis, getCenter=Vector.getCenter, isPlanar=Vector.isPlanar)


def _mv(value):
    """比べる側の om2.MVector を作る(MPoint の w は除く)。"""
    if isinstance(value, om2.MPoint):
        return om2.MVector(value.x, value.y, value.z)
    return om2.MVector(*list(value)[:3])


#: 相手のベクトルの候補(タプル・リスト・om2 の型・mlib の型・平行・反平行・0)。
OTHERS = (
    (4.0, -5.0, 6.0),
    [0, 1, 0],
    om2.MVector(-1.0, 0.5, 2.0),
    om2.MPoint(3.0, 3.0, -3.0),
    Vector(2.0, 4.0, 6.0),
    Translate(-1.0, -2.0, -3.0),
    (0.0, 0.0, 0.0),
)
#: 相手のベクトルの誤った値。成分の数が違う値(ValueError になる)と、文字列・並びでない値(TypeError になる)。
VALUE_BAD = ((1.0, 2.0), (1.0, 2.0, 3.0, 4.0), "abc")
TYPE_BAD = (None, 1.0, object())
OTHER_INVALID = VALUE_BAD + TYPE_BAD
#: 軸の候補(軸・ミラー面・番号・大文字)。
MIRROR_AXES = ("x", "y", "z", "YZ", "XZ", "XY", "zx", "yx", 0, 1, 2)
#: 点列の候補(同一平面・平面でない・3点以下・一直線・om2 の点)。
PLANAR = ((0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0), (2, 3, 0))
NONPLANAR = ((0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 2.0))
POINTS = (PLANAR, NONPLANAR, ((1, 2, 3),), [(0, 0, 0), (1, 1, 1), (2, 2, 2), (3, 3, 3)], [om2.MPoint(1, 0, 0), om2.MVector(0, 1, 0), Vector(0, 0, 1)])


def _expect_dot(case, call):
    case.assertAlmostEqual(call.result, _mv(call.target) * _mv(call.kwargs["other"]), places=9)


def _expect_cross(case, call):
    case.assertIsInstance(call.result, Vector)
    case.assertSequenceAlmostEqual(call.result, _mv(call.target) ^ _mv(call.kwargs["other"]))


def _expect_distance(case, call):
    length = (_mv(call.target) - _mv(call.kwargs["other"])).length()
    case.assertAlmostEqual(call.result, length * length if call.kwargs.get("squared") else length, places=9)


def _expect_angle(case, call):
    case.assertAlmostEqual(call.result, _mv(call.target).angle(_mv(call.kwargs["other"])), places=5)


def _expect_equivalent(case, call):
    case.assertIs(call.result, _mv(call.target).isEquivalent(_mv(call.kwargs["other"]), call.kwargs.get("tolerance", 1e-10)))


def _expect_lerp(case, call):
    a, b = _mv(call.target), _mv(call.kwargs["other"])
    case.assertSequenceAlmostEqual(call.result, a + (b - a) * call.kwargs["t"])


def _projected(target, axis):
    a, b = _mv(target), _mv(axis)
    return b * ((a * b) / (b * b))


def _expect_projected(case, call):
    case.assertSequenceAlmostEqual(call.result, _projected(call.target, call.kwargs["axis"]))


def _expect_orthogonal(case, call):
    case.assertSequenceAlmostEqual(call.result, _mv(call.target) - _projected(call.target, call.kwargs["axis"]))


def _expect_cotan(case, call):
    a, b = _mv(call.target), _mv(call.kwargs["other"])
    case.assertAlmostEqual(call.result, (a * b) / (a ^ b).length(), places=9)


def _expect_slerp(case, call):
    """om2 の MQuaternion で向きを回し、長さを線形補間した値と比べる(平行なときは長さだけ)。"""
    a, b = _mv(call.target), _mv(call.kwargs["other"])
    t, spin = call.kwargs["t"], call.kwargs.get("spin", 0)
    length = a.length() + (b.length() - a.length()) * t
    case.assertAlmostEqual(call.result.length(), abs(length), places=6)
    axis = a ^ b
    if axis.length() < 1e-9:
        return
    turn = (a.angle(b) + 2.0 * math.pi * spin) * t
    expected = a.normal().rotateBy(om2.MQuaternion(turn, axis.normal())) * length
    case.assertSequenceAlmostEqual(call.result, expected, places=6)


def _expect_mirror(case, call):
    axis = call.kwargs.get("axis", "x")
    pivot = list(call.kwargs.get("pivot", (0.0, 0.0, 0.0)))
    index = axis if isinstance(axis, int) else {"x": 0, "yz": 0, "zy": 0, "y": 1, "xz": 1, "zx": 1, "z": 2, "xy": 2, "yx": 2}[axis.lower()]
    expected = list(call.target)
    expected[index] = 2 * pivot[index] - expected[index]
    case.assertIs(type(call.result), type(call.target))
    case.assertSequenceAlmostEqual(call.result, expected)


def _expect_round(case, call):
    ndigits = call.kwargs.get("ndigits")
    case.assertEqual(list(call.result), [float(round(value, ndigits)) + 0.0 for value in call.target])


def _expect_zero(case, call):
    case.assertIs(call.result, call.target.length() <= call.kwargs.get("tolerance", 1e-10))


def _expect_closest(case, call):
    values = list(call.target)
    if call.kwargs.get("includeNegative", True):
        index = max(range(3), key=lambda number: abs(values[number]))
        name = ("-" if values[index] < 0 else "") + "xyz"[index]
    else:
        name = "xyz"[max(range(3), key=lambda number: values[number])]
    case.assertEqual(call.result, name)


def _expect_from_axis(case, call):
    axis = call.kwargs["axis"]
    index = "xyz".index(axis[-1].lower())
    expected = om2.MVector()
    expected[index] = -1.0 if axis.startswith("-") else 1.0
    case.assertSequenceAlmostEqual(call.result, expected)


def _expect_center(case, call):
    points = [_mv(point) for point in call.kwargs["points"]]
    total = om2.MVector()
    for point in points:
        total += point
    case.assertSequenceAlmostEqual(call.result, total / len(points))


def _expect_planar(case, call):
    points = call.kwargs["points"]
    tolerance = call.kwargs.get("tolerance", 1e-10)
    case.assertIs(call.result, points is not NONPLANAR or tolerance >= 2.0)


def _invalid_tolerance():
    return {"tolerance": ("a", None, float("nan"), float("inf"), -1.0, True)}


METHODS = (
    Method("dot", _vector, args=((1.0, 0.0, 0.0),), values={"other": OTHERS}, invalid={"other": OTHER_INVALID}, expect=_expect_dot, state=_value, writes=False),
    Method(
        "cross", _vector, args=((1.0, 0.0, 0.0),), values={"other": OTHERS}, invalid={"other": OTHER_INVALID}, expect=_expect_cross, state=_value, writes=False
    ),
    Method(
        "distanceTo",
        _vector,
        args=((1.0, 0.0, 0.0),),
        values={"other": OTHERS},
        invalid={"other": OTHER_INVALID, "squared": (1, "yes", None)},
        expect=_expect_distance,
        state=_value,
        writes=False,
    ),
    Method(
        "angleTo",
        _vector,
        args=((1.0, 0.0, 0.0),),
        values={"other": OTHERS},
        invalid={"other": OTHER_INVALID},
        expect=_expect_angle,
        state=_value,
        writes=False,
    ),
    Method(
        "isEquivalent",
        _vector,
        args=((1.0, 2.0, 3.0),),
        values={"other": (*OTHERS, (1.0, 2.0, 3.0 + 1e-12)), "tolerance": (0.0, 1e-10, 0.5, 100.0)},
        replace=("tolerance",),
        invalid={"other": OTHER_INVALID, "tolerance": ("a", None, -1.0)},
        expect=_expect_equivalent,
        state=_value,
        writes=False,
    ),
    Method(
        "lerp",
        _vector,
        args=((3.0, 0.0, 0.0), 0.5),
        values={"other": OTHERS, "t": (0.0, 0.5, 1.0, -1.5, 2.0)},
        invalid={"other": OTHER_INVALID, "t": ("a", None, float("nan"), float("inf"))},
        expect=_expect_lerp,
        state=_value,
        writes=False,
    ),
    Method(
        "projected",
        _vector,
        args=((0.0, 2.0, 0.0),),
        values={"axis": OTHERS},
        invalid={"axis": OTHER_INVALID},
        expect=_expect_projected,
        state=_value,
        writes=False,
    ),
    Method(
        "orthogonal",
        _vector,
        args=((0.0, 2.0, 0.0),),
        values={"axis": OTHERS},
        invalid={"axis": OTHER_INVALID},
        expect=_expect_orthogonal,
        state=_value,
        writes=False,
    ),
    Method(
        "cotan", _vector, args=((1.0, 0.0, 0.0),), values={"other": OTHERS}, invalid={"other": OTHER_INVALID}, expect=_expect_cotan, state=_value, writes=False
    ),
    Method(
        "slerp",
        _vector,
        args=((0.0, 4.0, 0.0), 0.5),
        values={"other": OTHERS, "t": (0.0, 0.25, 1.0, -0.5, 1.5), "spin": (0, 1, -1, 2)},
        replace=("spin",),
        invalid={"other": OTHER_INVALID, "t": ("a", None, float("nan"), float("inf")), "spin": (1.0, True, "a", None)},
        expect=_expect_slerp,
        state=_value,
        writes=False,
    ),
    Method(
        "mirror",
        _vector,
        values={"axis": MIRROR_AXES, "pivot": ((0.0, 0.0, 0.0), [1, 2, 3], om2.MVector(-1.0, 0.5, 4.0), om2.MPoint(2.0, 2.0, 2.0), Vector(0.5, 0.5, 0.5))},
        replace=("axis",),
        invalid={"axis": ("w", "xyz", "", 3, -1, 1.5, None, True), "pivot": ((1.0, 2.0), "abc", None, (float("nan"), 0.0, 0.0), object())},
        expect=_expect_mirror,
        state=_value,
        writes=False,
    ),
    Method(
        "round",
        lambda case: Vector(1.23456, -2.5, 1234.5),
        values={"ndigits": (None, 0, 1, 3, -1, -3, 20)},
        replace=("ndigits",),
        invalid={"ndigits": (1.5, True, "1")},
        expect=_expect_round,
        state=_value,
        writes=False,
    ),
    Method(
        "isZero",
        _vector,
        values={"tolerance": (0.0, 1e-10, 3.7, 3.75, 1000.0)},
        replace=("tolerance",),
        invalid=_invalid_tolerance(),
        expect=_expect_zero,
        state=_value,
        writes=False,
    ),
    Method(
        "getClosestAxis", lambda case: Vector(1.0, -5.0, 3.0), invalid={"includeNegative": (1, "yes", None)}, expect=_expect_closest, state=_value, writes=False
    ),
    Method(
        "fromAxis",
        _classes,
        args=("x",),
        values={"axis": ("x", "y", "z", "-x", "-y", "-z", "+x", "X", "-Y")},
        replace=("axis",),
        invalid={"axis": ("w", " x", "", "xy", 0, None, 1.5)},
        expect=_expect_from_axis,
        writes=False,
    ),
    Method(
        "getCenter",
        _classes,
        args=(PLANAR,),
        values={"points": POINTS},
        replace=("points",),
        invalid={"points": ((), 1.0, None, ((1.0, 2.0),), ("abc",))},
        expect=_expect_center,
        writes=False,
    ),
    Method(
        "isPlanar",
        _classes,
        args=(PLANAR,),
        values={"points": POINTS, "tolerance": (0.0, 1e-10, 1.0, 1000.0)},
        replace=("points", "tolerance"),
        invalid={"points": (1.0, None), **_invalid_tolerance()},
        expect=_expect_planar,
        writes=False,
    ),
)


class VectorArgumentSweepTest(ArgumentSweepCase):
    """Vectorの公開メソッドの引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
