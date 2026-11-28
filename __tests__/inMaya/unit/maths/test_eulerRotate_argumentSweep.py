"""EulerRotate と orderIndex の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

結果は om2 の同じ計算(``MEulerRotation`` の比較・並べ替え、``MMatrix`` の積と ``MTransformationMatrix`` の分解)と
突き合わせる。数学型はシーンを変えないので、Undo・fast の性質は当てはまらない(表は ``writes=False`` にし、
状態は対象の値にして、メソッドが自身を変えないことを確かめる)。
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
from support.argumentTable import Method, same

from mlib.maths import EulerRotate, Matrix, Quaternion, Vector, eulerRotate

ORDER_NAMES = ("xyz", "yzx", "zxy", "xzy", "yxz", "zyx")


def _host(owner, **functions):
    """関数・クラスメソッドを、表の対象のメソッドとして呼べるようにする(部品は対象の型からメソッドを読むため)。"""

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
    """値の状態(3成分と回転順序)。メソッドが自身を変えないことを確かめる。"""
    return [target.x, target.y, target.z, target.order] if isinstance(target, om2.MEulerRotation) else None


def _rotation(case):
    return EulerRotate(0.3, -1.2, 2.5, order="yzx")


def _functions(case):
    return _host("EulerRotate", orderIndex=eulerRotate.orderIndex, fromYawPitch=EulerRotate.fromYawPitch)


def _index(order):
    return order if isinstance(order, int) else ORDER_NAMES.index(order.lower())


def _mq(value):
    return om2.MEulerRotation(value.x, value.y, value.z, value.order).asQuaternion()


def _assert_rotation(case, actual, expected, places=6):
    a, b = _mq(actual), _mq(expected)
    case.assertAlmostEqual(abs(a.x * b.x + a.y * b.y + a.z * b.z + a.w * b.w), 1.0, places=places)


ORDERS = (*ORDER_NAMES, "XYZ", "Zyx", 0, 1, 2, 3, 4, 5)
ORDER_INVALID = ("xxy", "", "x", 6, -1, True, 1.5, None)
DIRECTIONS = ((1.0, 0.0, 0.0), [0, 2, 0], (0.0, 0.0, -3.0), om2.MVector(1.0, 1.0, 1.0), om2.MPoint(-2.0, 0.5, 0.0), Vector(0.3, -0.4, 0.5), (0.0, 1.0, 0.0))


def _expect_order_index(case, call):
    case.assertEqual(call.result, _index(call.kwargs["order"]))
    case.assertEqual(call.result, getattr(om2.MEulerRotation, "k" + ORDER_NAMES[call.result].upper()))


def _expect_yaw_pitch(case, call):
    """基準軸(回転順序の最初の軸)の行が direction の向きになり、基準軸の周りの回転は0。"""
    direction = call.kwargs["direction"]
    direction = om2.MVector(direction.x, direction.y, direction.z) if isinstance(direction, (om2.MVector, om2.MPoint)) else om2.MVector(*direction)
    index = _index(call.kwargs.get("order", "xyz"))
    base = "xyz".index(ORDER_NAMES[index][0])
    case.assertEqual(call.result.order, index)
    case.assertAlmostEqual(call.result[base], 0.0, places=12)
    matrix = om2.MEulerRotation(call.result.x, call.result.y, call.result.z, index).asMatrix()
    row = om2.MVector(*(matrix.getElement(base, column) for column in range(3)))
    case.assertSequenceAlmostEqual(row, direction.normal())


def _expect_mirror(case, call):
    axis = call.kwargs.get("axis", "x")
    index = axis if isinstance(axis, int) else {"x": 0, "yz": 0, "zy": 0, "y": 1, "xz": 1, "zx": 1, "z": 2, "xy": 2, "yx": 2}[axis.lower()]
    flip = om2.MMatrix()
    for column in range(3):
        flip.setElement(column, column, 1.0 if column == index else -1.0)
    source = om2.MEulerRotation(call.target.x, call.target.y, call.target.z, call.target.order)
    expected = om2.MTransformationMatrix(source.asMatrix() * flip).rotation().reorder(call.target.order)
    case.assertIs(type(call.result), type(call.target))
    case.assertEqual(call.result.order, call.target.order)
    _assert_rotation(case, call.result, expected)


def _expect_round(case, call):
    ndigits = call.kwargs.get("ndigits")
    unit = call.kwargs.get("unit", "deg")
    degrees = unit is None or unit.startswith("deg")
    expected = []
    for value in (call.target.x, call.target.y, call.target.z):
        if degrees:
            expected.append(math.radians(round(math.degrees(value), ndigits)))
        else:
            expected.append(float(round(value, ndigits)))
    case.assertEqual(call.result.order, call.target.order)
    case.assertSequenceAlmostEqual([call.result.x, call.result.y, call.result.z], expected, places=12)


def _expect_equivalent(case, call):
    other = call.kwargs["other"]
    other = other if isinstance(other, om2.MEulerRotation) else om2.MEulerRotation(*other)
    source = om2.MEulerRotation(call.target.x, call.target.y, call.target.z, call.target.order)
    case.assertIs(call.result, source.isEquivalent(other, call.kwargs.get("tolerance", 1e-10)))


def _expect_gimbal(case, call):
    middle = "xyz".index(ORDER_NAMES[call.target.order][1])
    angle = math.remainder(call.target[middle], 2.0 * math.pi)
    case.assertIs(call.result, abs(abs(angle) - math.pi / 2.0) <= call.kwargs.get("tolerance", 1e-10))


TOLERANCE_INVALID = {"tolerance": ("a", None, float("nan"), float("inf"), -1.0, True)}
OTHER_INVALID = ((1.0, 2.0), "abc", None, 1.0, object())


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


def _me(value):
    """比べる側の om2.MEulerRotation を作る。"""
    return om2.MEulerRotation(value.x, value.y, value.z, value.order)


def _parts(value):
    """om2・mlib の値を、比べられる数の並びにする。"""
    if isinstance(value, om2.MEulerRotation):
        return [value.x, value.y, value.z, value.order]
    if isinstance(value, om2.MQuaternion):
        return [value.x, value.y, value.z, value.w]
    return list(value)


_SAMPLE_MATRIX = Matrix(translate=(1.0, 2.0, 3.0), rotate=(0.4, -0.2, 1.3), scale=(1.0, 2.0, 3.0))
#: コンストラクターの位置引数の候補(なし・3成分・回転順序つき・並び・コピー)。
INIT_ARGS = (
    (),
    (0.1, 0.2, 0.3),
    (0.1, 0.2, 0.3, "zxy"),
    (1, -2, 3, 3),
    ((0.5, 0.25, -0.75),),
    ([0.5, 0.25, -0.75], "yzx"),
    (om2.MEulerRotation(0.3, -1.2, 2.5, om2.MEulerRotation.kYZX),),
    (EulerRotate(0.3, -1.2, 2.5, order="zyx"),),
)
#: コンストラクターのキーワード引数の候補(回転順序・単位・成分)。
INIT_KWARGS = (
    {},
    {"order": "zyx"},
    {"order": 4},
    {"unit": "deg"},
    {"unit": "radians"},
    {"unit": None},
    {"order": "yxz", "unit": "degree"},
    {"x": 0.5},
    {"x": 90.0, "z": -45.0, "unit": "deg"},
    {"x": 0.1, "y": 0.2, "z": 0.3, "order": 1},
)
#: コンストラクターの誤った位置引数(成分が数でない・引数の数・回転順序)と、誤ったキーワード引数(知らない名前・単位・回転順序)。
INIT_ARGS_INVALID = (("a", 0.0, 0.0), (1.0,), (1.0, 2.0), (1.0, 2.0, 3.0, "xxy"), (1.0, 2.0, 3.0, 4, 5), (None,), ((1.0, 2.0),), (object(),))
INIT_KWARGS_INVALID = ({"w": 1.0}, {"unit": "grad"}, {"unit": 1.5}, {"order": "abc"}, {"order": 6}, {"x": "a"})
#: 回転を1つ受ける静的メソッドの候補(一周を超える角度・om2 と mlib の型)。
SOURCES = ((om2.MEulerRotation(4.0, -5.0, 7.0, om2.MEulerRotation.kYZX),), (EulerRotate(0.3, -1.2, 2.5, order="zxy"),), (om2.MEulerRotation(),))
#: 元の回転と基準を受ける静的メソッドの候補。
SOURCE_TARGETS = (
    (om2.MEulerRotation(0.3, -1.2, 2.5, om2.MEulerRotation.kYZX), om2.MEulerRotation(7.0, 6.0, -8.0, om2.MEulerRotation.kYZX)),
    (EulerRotate(4.0, -5.0, 7.0), EulerRotate(0.0, 0.0, 0.0)),
    (EulerRotate(0.1, 0.2, 0.3, order="zxy"), om2.MEulerRotation(-3.5, 3.5, 12.0, om2.MEulerRotation.kZXY)),
)
#: 基準を受けるメソッドの候補(対象と同じ回転順序)。
CLOSEST_TARGETS = (
    (om2.MEulerRotation(7.0, 6.0, -8.0, om2.MEulerRotation.kYZX),),
    (EulerRotate(-6.0, 0.1, 9.0, order="yzx"),),
    (om2.MEulerRotation(0.0, 0.0, 0.0, om2.MEulerRotation.kYZX),),
)
#: decompose の候補(マトリクスと回転順序の定数)。
DECOMPOSES = (
    (om2.MMatrix(_SAMPLE_MATRIX), om2.MEulerRotation.kXYZ),
    (_SAMPLE_MATRIX, om2.MEulerRotation.kZXY),
    (om2.MMatrix(), om2.MEulerRotation.kZYX),
    (_SAMPLE_MATRIX, 1),
)
#: reorder の候補(回転順序の定数)。
REORDERS = tuple((order,) for order in range(6))


def _known_unit_none(stage, kwargs):
    """数の成分に ``unit=None`` を足した場合(docstring の既定は ``"rad"`` だが、None は度として読まれる)。"""
    args, keywords = kwargs.get("args", ()), kwargs.get("kwargs", {})
    return stage != "invalid" and "unit" in keywords and keywords["unit"] is None and bool(args) and not isinstance(args[0], om2.MEulerRotation)


def _expect_init(case, call):
    """成分・回転順序を、引数の形ごとに読んだ値と比べる(度は om2 と同じラジアンで持つ)。"""
    args, kwargs = call.kwargs.get("args", ()), call.kwargs.get("kwargs", {})
    case.assertIs(type(call.result), EulerRotate)
    if any(name in kwargs for name in "xyz"):
        if args:
            return
        values, order = [kwargs.get(name, 0.0) for name in "xyz"], kwargs.get("order", 0)
    else:
        source = args[0] if len(args) in (1, 2) else args[:3]
        copied = isinstance(source, om2.MEulerRotation)
        values = [source.x, source.y, source.z] if copied else (list(source) if args else [0.0, 0.0, 0.0])
        order = kwargs.get("order", args[-1] if len(args) in (2, 4) else (source.order if copied else 0))
    if str(kwargs.get("unit")).lower().startswith("deg"):
        values = [math.radians(value) for value in values]
    case.assertSequenceAlmostEqual([call.result.x, call.result.y, call.result.z], values, places=12)
    case.assertEqual(call.result.order, _index(order))


def _same_as(name, kind=EulerRotate, static=False):
    """om2.MEulerRotation の同じ名前のメソッドを同じ引数で呼んだ結果と同じで、戻り値は kind の型(static は静的メソッド)。"""

    def expect(case, call):
        args = call.kwargs.get("args", ())
        function = getattr(om2.MEulerRotation, name)
        expected = function(*args) if static else function(_me(call.target), *args)
        case.assertIs(type(call.result), kind)
        case.assertTrue(same(_parts(call.result), _parts(expected), 9), f"om2.MEulerRotation.{name} と違う: {call.result!r} と {expected!r}")

    return expect


def _expect_degrees(case, call):
    case.assertIs(type(call.result), tuple)
    case.assertSequenceAlmostEqual(call.result, [math.degrees(value) for value in (call.target.x, call.target.y, call.target.z)], places=9)


def _expect_reverse(case, call):
    """マトリクスは同じで、クォータニオンの符号が反対になる(om2 の asMatrix・asQuaternion で比べる)。"""
    case.assertIs(type(call.result), type(call.target))
    case.assertEqual(call.result.order, call.target.order)
    case.assertSequenceAlmostEqual(list(_me(call.result).asMatrix()), list(_me(call.target).asMatrix()), places=9)
    a, b = _mq(call.result), _mq(call.target)
    case.assertAlmostEqual(a.x * b.x + a.y * b.y + a.z * b.z + a.w * b.w, -1.0, places=9)


METHODS = (
    Method(
        "orderIndex",
        _functions,
        args=("xyz",),
        values={"order": ORDERS},
        replace=("order",),
        invalid={"order": ORDER_INVALID},
        expect=_expect_order_index,
        writes=False,
    ),
    Method(
        "fromYawPitch",
        _functions,
        args=((1.0, 0.0, 0.0),),
        values={"direction": DIRECTIONS, "order": ORDERS},
        replace=("direction", "order"),
        invalid={"direction": ((0.0, 0.0, 0.0), (1.0, 2.0), (float("nan"), 0.0, 0.0), "abc", None, 1.0, object()), "order": ORDER_INVALID},
        expect=_expect_yaw_pitch,
        writes=False,
    ),
    Method(
        "mirror",
        _rotation,
        values={"axis": ("x", "y", "z", "YZ", "XZ", "XY", "zx", 0, 1, 2)},
        replace=("axis",),
        invalid={"axis": ("w", "xyz", "", 3, -1, 1.5, None, True)},
        expect=_expect_mirror,
        state=_value,
        writes=False,
    ),
    Method(
        "round",
        _rotation,
        values={"ndigits": (None, 0, 1, 3, -1, 20), "unit": ("deg", "rad", "degree", "radians", None)},
        replace=("ndigits", "unit"),
        invalid={"ndigits": (1.5, True, "1"), "unit": ("grad", "frame", "", 1.5, True)},
        expect=_expect_round,
        state=_value,
        writes=False,
    ),
    Method(
        "isEquivalent",
        _rotation,
        args=((0.0, 0.0, 0.0),),
        values={
            "other": (
                (0.3, -1.2, 2.5),
                [0, 0, 0],
                om2.MEulerRotation(0.3, -1.2, 2.5, om2.MEulerRotation.kYZX),
                EulerRotate(0.3, -1.2, 2.5 + 1e-12, order="yzx"),
                EulerRotate(0.3, -1.2, 2.5),
            ),
            "tolerance": (0.0, 1e-10, 0.5, 100.0),
        },
        replace=("other", "tolerance"),
        invalid={"other": OTHER_INVALID, "tolerance": ("a", None, -1.0)},
        expect=_expect_equivalent,
        state=_value,
        writes=False,
    ),
    Method(
        "isGimbalLocked",
        lambda case: EulerRotate(0.3, math.radians(90.5), 2.5, order="xyz"),
        values={"tolerance": (0.0, 1e-10, 0.008, 0.009, 1000.0)},
        replace=("tolerance",),
        invalid=TOLERANCE_INVALID,
        expect=_expect_gimbal,
        state=_value,
        writes=False,
    ),
    Method(
        "__init__",
        _rotation,
        function=_constructor(EulerRotate),
        values={"*": INIT_ARGS, "**": INIT_KWARGS},
        invalid={"*": INIT_ARGS_INVALID, "**": INIT_KWARGS_INVALID},
        expect=_expect_init,
        state=_value,
        writes=False,
    ),
    Method(
        "computeAlternateSolution",
        _rotation,
        args=SOURCES[0],
        values={"*": SOURCES},
        expect=_same_as("computeAlternateSolution", static=True),
        state=_value,
        writes=False,
    ),
    Method("computeBound", _rotation, args=SOURCES[0], values={"*": SOURCES}, expect=_same_as("computeBound", static=True), state=_value, writes=False),
    Method(
        "computeClosestCut",
        _rotation,
        args=SOURCE_TARGETS[0],
        values={"*": SOURCE_TARGETS},
        expect=_same_as("computeClosestCut", static=True),
        state=_value,
        writes=False,
    ),
    Method(
        "computeClosestSolution",
        _rotation,
        args=SOURCE_TARGETS[0],
        values={"*": SOURCE_TARGETS},
        expect=_same_as("computeClosestSolution", static=True),
        state=_value,
        writes=False,
    ),
    Method("decompose", _rotation, args=DECOMPOSES[0], values={"*": DECOMPOSES}, expect=_same_as("decompose", static=True), state=_value, writes=False),
    Method("asDegrees", _rotation, expect=_expect_degrees, state=_value, writes=False),
    Method("asQuaternion", _rotation, expect=_same_as("asQuaternion", Quaternion), state=_value, writes=False),
    Method("asMatrix", _rotation, expect=_same_as("asMatrix", Matrix), state=_value, writes=False),
    Method("alternateSolution", _rotation, expect=_same_as("alternateSolution"), state=_value, writes=False),
    Method("bound", lambda case: EulerRotate(4.0, -5.0, 7.0, order="zxy"), expect=_same_as("bound"), state=_value, writes=False),
    Method("closestCut", _rotation, args=CLOSEST_TARGETS[0], values={"*": CLOSEST_TARGETS}, expect=_same_as("closestCut"), state=_value, writes=False),
    Method(
        "closestSolution", _rotation, args=CLOSEST_TARGETS[0], values={"*": CLOSEST_TARGETS}, expect=_same_as("closestSolution"), state=_value, writes=False
    ),
    Method("inverse", _rotation, expect=_same_as("inverse"), state=_value, writes=False),
    Method("reorder", _rotation, args=REORDERS[2], values={"*": REORDERS}, expect=_same_as("reorder"), state=_value, writes=False),
    Method("asVector", _rotation, expect=_same_as("asVector", Vector), state=_value, writes=False),
    Method("reverseDirection", _rotation, expect=_expect_reverse, state=_value, writes=False),
)


class EulerRotateArgumentSweepTest(ArgumentSweepCase):
    """EulerRotate と orderIndex の公開メソッドの引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
