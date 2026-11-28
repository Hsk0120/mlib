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
from support.argumentTable import ErrorState, Method, same

from mlib.maths import EulerRotate, Matrix, Quaternion, Translate, Vector


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


def _constructor(cls):
    """コンストラクターを、``__init__`` の署名と docstring を持つ関数にする。

    クラスをそのまま ``function=`` に渡すと、署名は ``__new__`` の ``*args, **kwargs``、docstring はクラスの説明になり、
    ``__init__`` の Args・Raises を読めない。
    """

    def construct(*args, **kwargs):
        return cls(*args, **kwargs)

    signature = inspect.signature(cls.__init__)
    construct.__signature__ = signature.replace(parameters=list(signature.parameters.values())[1:])
    construct.__doc__ = cls.__init__.__doc__
    return construct


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


#: コンストラクターの位置引数の候補(なし・3成分・2成分・並び・om2 の型・mlib の型)。
INIT_ARGS = (
    (),
    (1.0, 2.0, 3.0),
    (4, -5),
    ((4.0, -5.0, 6.0),),
    ([0, 1, 0],),
    (om2.MVector(-1.0, 0.5, 2.0),),
    (om2.MPoint(3.0, 3.0, -3.0),),
    (om2.MFloatVector(1.0, 2.0, 4.0),),
    (Translate(-1.0, -2.0, -3.0),),
)
#: コンストラクターのキーワード引数の候補。
INIT_KWARGS = ({}, {"x": 1.5}, {"y": 2.0, "z": -3.0}, {"x": 1, "y": 2, "z": 3})
#: コンストラクターの誤った位置引数(成分が数でない・成分の数が多い)と、誤ったキーワード引数(知らない名前・数でない成分)。
INIT_ARGS_INVALID = (("a", 0.0, 0.0), ("abc",), (None,), (1.0, 2.0, 3.0, 4.0, 5.0), (object(),))
INIT_KWARGS_INVALID = ({"w": 1.0}, {"x": "a"})
#: rotateBy の候補(クォータニオン・オイラー回転・軸の定数と角度)。
ROTATIONS = (
    (om2.MQuaternion(0.7, om2.MVector(0.0, 1.0, 0.0)),),
    (Quaternion(0.1, 0.2, 0.3, 0.9),),
    (om2.MEulerRotation(0.1, 0.2, 0.3),),
    (EulerRotate(0.3, 0.2, 0.1, order="zxy"),),
    (om2.MVector.kXaxis, 0.5),
    (om2.MVector.kZaxis, -1.25),
)
#: rotateTo の候補(om2・mlib の方向。同じ向き・反対の向きを含む)。
TARGETS = ((om2.MVector(0.0, 1.0, 0.0),), (Vector(-3.0, 0.5, 2.0),), (om2.MVector(2.0, 4.0, 6.0),), (Translate(-1.0, -2.0, -3.0),))
#: transformAsNormal の候補(単位・スケールと回転を持つマトリクス。om2 と mlib の型)。
NORMAL_MATRICES = (
    (om2.MMatrix(),),
    (Matrix(translate=(1.0, 2.0, 3.0), rotate=(0.1, 0.2, 0.3), scale=(1.0, 2.0, 3.0)),),
    (om2.MMatrix(Matrix(rotate=(0.5, 0.0, -0.25), scale=(2.0, 2.0, 0.5))),),
)
#: 重心座標の点の候補(2点・3点。タプル・リスト・om2 の型・mlib の型)。
WEIGHT_POINTS = (
    ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0)),
    ([1, 1, 1], om2.MVector(4.0, 5.0, 6.0)),
    ((0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (0.0, 4.0, 0.0)),
    (om2.MPoint(1.0, 0.0, 0.0), Vector(0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
)
#: 重心座標の点の誤った値(点の数・長さ0の線分・一直線の3点・成分の数・数でない値)。
WEIGHT_POINTS_INVALID = (
    (),
    ((0.0, 0.0, 0.0),),
    ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    ((1.0, 1.0, 1.0), (1.0, 1.0, 1.0)),
    ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0), (2.0, 2.0, 2.0)),
    ((1.0, 2.0), (3.0, 4.0)),
    (None, (1.0, 0.0, 0.0)),
    (1.0, 2.0),
)


def _expect_init(case, call):
    """キーワードが無ければ om2.MVector の同じ引数、あれば位置引数の続きをキーワードで埋めた成分と同じ。"""
    args, kwargs = call.kwargs.get("args", ()), call.kwargs.get("kwargs", {})
    case.assertIs(type(call.result), Vector)
    if not kwargs:
        case.assertSequenceAlmostEqual(call.result, om2.MVector(*args))
    elif all(_is_number(value) for value in args):
        expected = dict(zip("xyz", args), **kwargs)
        case.assertSequenceAlmostEqual(call.result, [expected.get(name, 0.0) for name in "xyz"])


def _same_as(name, kind=None):
    """om2.MVector の同じ名前のメソッドを同じ引数で呼んだ結果と同じ(kind を書けば、戻り値の型も確かめる)。"""

    def expect(case, call):
        expected = getattr(om2.MVector, name)(_mv(call.target), *call.kwargs.get("args", ()))
        if kind is not None:
            case.assertIs(type(call.result), kind)
        case.assertTrue(same(call.result, expected, 9), f"om2.MVector.{name} と違う: {call.result!r} と {expected!r}")

    return expect


def _expect_length_sq(case, call):
    case.assertAlmostEqual(call.result, _mv(call.target) * _mv(call.target), places=9)


def _expect_abs(case, call):
    case.assertIs(type(call.result), type(call.target))
    case.assertSequenceAlmostEqual(call.result, [math.fabs(value) for value in _mv(call.target)])


def _expect_weights(case, call):
    """ウェイトの合計は1で、ウェイトで混ぜた位置と自身の差は、線分・三角形の辺と直交する(射影した位置)。"""
    points = [_mv(point) for point in call.kwargs["points"]]
    case.assertEqual(len(call.result), len(points))
    case.assertAlmostEqual(sum(call.result), 1.0, places=9)
    mixed = om2.MVector()
    for point, weight in zip(points, call.result):
        mixed += point * weight
    for point in points[1:]:
        case.assertAlmostEqual((_mv(call.target) - mixed) * (point - points[0]), 0.0, places=9)


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
    Method(
        "__init__",
        _vector,
        function=_constructor(Vector),
        values={"*": INIT_ARGS, "**": INIT_KWARGS},
        invalid={"*": INIT_ARGS_INVALID, "**": INIT_KWARGS_INVALID},
        expect=_expect_init,
        state=_value,
        writes=False,
    ),
    Method("lengthSq", _vector, expect=_expect_length_sq, state=_value, writes=False),
    Method("normal", _vector, expect=_same_as("normal", Vector), state=_value, writes=False),
    Method("rotateBy", _vector, args=ROTATIONS[0], values={"*": ROTATIONS}, expect=_same_as("rotateBy", Vector), state=_value, writes=False),
    Method("rotateTo", _vector, args=TARGETS[0], values={"*": TARGETS}, expect=_same_as("rotateTo", Quaternion), state=_value, writes=False),
    Method(
        "transformAsNormal",
        _vector,
        args=NORMAL_MATRICES[0],
        values={"*": NORMAL_MATRICES},
        expect=_same_as("transformAsNormal", Vector),
        state=_value,
        writes=False,
    ),
    Method(
        "unit",
        _vector,
        expect=_same_as("normal", Vector),
        state=_value,
        writes=False,
        errors=(ErrorState("0のベクトル", lambda case, target: Vector(), ValueError),),
    ),
    Method("abs", lambda case: Translate(1.0, -5.0, 3.0), expect=_expect_abs, state=_value, writes=False),
    Method(
        "getBarycentricWeights",
        _vector,
        args=WEIGHT_POINTS[0],
        values={"points": WEIGHT_POINTS},
        invalid={"points": WEIGHT_POINTS_INVALID},
        expect=_expect_weights,
        state=_value,
        writes=False,
    ),
)


class VectorArgumentSweepTest(ArgumentSweepCase):
    """Vectorの公開メソッドの引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
