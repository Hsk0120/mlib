"""EulerRotate と orderIndex の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

結果は om2 の同じ計算(``MEulerRotation`` の比較・並べ替え、``MMatrix`` の積と ``MTransformationMatrix`` の分解)と
突き合わせる。数学型はシーンを変えないので、Undo・fast の性質は当てはまらない(表は ``writes=False`` にし、
状態は対象の値にして、メソッドが自身を変えないことを確かめる)。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import inspect
import math
import re
import sys
import unittest

import maya.api.OpenMaya as om2

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Method

from mlib.maths import EulerRotate, Vector, eulerRotate

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


def _known(name, values, reason):
    """段2の場合の名前を、fnmatch の記号([ など)を文字として扱う形にして返す。"""
    return {"invalid:" + re.sub(r"([*?[])", r"[\1]", f"{name}={value!r}"): reason for value in values}


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

#: 本体との食い違い(findings4/sweep-common-json-maths.md の M3)。Raises が無いのに TypeError・ValueError になる値と、負の tolerance。
KNOWN_EQUIVALENT = {
    **_known("other", OTHER_INVALID, "Raises が無いのに TypeError・ValueError になる(回転にできない値)"),
    **_known("tolerance", ("a", None), "Raises が無いのに TypeError になる(om2 へそのまま渡す)"),
    "invalid:tolerance=-1.0": "負の tolerance を受け付ける",
}

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
        known=KNOWN_EQUIVALENT,
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
)


class EulerRotateArgumentSweepTest(ArgumentSweepCase):
    """EulerRotate と orderIndex の公開メソッドの引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
