"""Quaternionの公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

結果は om2 の同じ計算(``MQuaternion`` の作成・slerp・回転、``MEulerRotation.decompose``)と突き合わせる。
数学型はシーンを変えないので、Undo・fast の性質は当てはまらない(表は ``writes=False`` にし、
状態は対象の4成分にして、メソッドが自身を変えないことを確かめる)。
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

from mlib.maths import EulerRotate, Quaternion, Vector


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


def _known(name, values, reason):
    """段2の場合の名前を、fnmatch の記号([ など)を文字として扱う形にして返す。"""
    return {"invalid:" + re.sub(r"([*?[])", r"[\1]", f"{name}={value!r}"): reason for value in values}


def _value(case, target):
    """値の状態(4成分)。メソッドが自身を変えないことを確かめる。"""
    return [target.x, target.y, target.z, target.w] if isinstance(target, om2.MQuaternion) else None


def _rotation(case):
    return Quaternion(om2.MQuaternion(0.7, om2.MVector(1.0, 2.0, 0.5)))


def _classes(case):
    return _host("Quaternion", fromAxisAngle=Quaternion.fromAxisAngle, fromRollBend=Quaternion.fromRollBend)


def _mq(value):
    return om2.MQuaternion(value.x, value.y, value.z, value.w)


def _mv(value):
    if isinstance(value, om2.MPoint):
        return om2.MVector(value.x, value.y, value.z)
    return om2.MVector(*list(value)[:3])


def _unit(kwargs):
    """unit の指定。None は度として扱う(findings4/sweep-common-json-maths.md の M8)。"""
    unit = kwargs.get("unit", "rad")
    return "deg" if unit is None else unit


def _radians(value, unit):
    return math.radians(value) if unit in ("deg", "degree", "degrees") else value


def _assert_rotation(case, actual, expected, places=6):
    """2つのクォータニオンが同じ回転(符号の違いは同じ)であることを確かめる。"""
    a, b = _mq(actual).normal(), _mq(expected).normal()
    case.assertAlmostEqual(abs(a.x * b.x + a.y * b.y + a.z * b.z + a.w * b.w), 1.0, places=places)


#: 相手の回転の候補(om2・mlib・単位でない・反対の符号・同じ回転)。
OTHERS = (
    om2.MQuaternion(),
    Quaternion(0.0, 0.7071, 0.0, 0.7071),
    om2.MQuaternion(0.2, 0.4, 0.1, 2.0),
    om2.MQuaternion(-0.1, -0.2, -0.3, -0.9),
    Quaternion(om2.MQuaternion(0.7, om2.MVector(1.0, 2.0, 0.5))),
)
#: 相手の回転の誤った値(0のクォータニオン・x,y,z,w を持たない値)。
OTHER_INVALID = (om2.MQuaternion(0.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), None, 1.0, "abc")
#: 3成分の候補。
XYZ = ((1.0, 0.0, 0.0), [0, 2, 0], om2.MVector(1.0, 1.0, 1.0), om2.MPoint(0.0, 0.0, -3.0), Vector(0.3, -0.4, 0.5))
XYZ_INVALID = ((0.0, 0.0, 0.0), (1.0, 2.0), "abc", None, 1.0, object())
#: 角度の単位(既定・別名・None)。
UNITS = ("rad", "deg", "degree", "radians", None)
UNIT_INVALID = ("grad", "frame", "", 1.5, True)
AXES = ("x", "y", "z", "-x", "-y", "-z")
ORDERS = ("xyz", "yzx", "zxy", "xzy", "yxz", "zyx", "ZYX", 0, 3, 5)


def _expect_axis_angle(case, call):
    unit = _unit(call.kwargs)
    expected = om2.MQuaternion(_radians(call.kwargs["angle"], unit), _mv(call.kwargs["axis"]).normal())
    case.assertIsInstance(call.result, Quaternion)
    case.assertSequenceAlmostEqual(_value(case, call.result), _value(case, expected))


def _expect_roll_bend(case, call):
    """作った回転で aimAxis を回すと、om2 で roll・曲げを順に当てた向きになり、asRollBend で同じ角度に戻る。"""
    kwargs = call.kwargs
    unit = _unit(kwargs)
    angles = [_radians(kwargs[name], unit) for name in ("roll", "bendH", "bendV")]
    q = _mq(call.result)
    case.assertAlmostEqual(q.x * q.x + q.y * q.y + q.z * q.z + q.w * q.w, 1.0, places=9)
    if all(abs(angle) < math.pi * 0.99 for angle in angles):
        back = call.result.asRollBend(aimAxis=kwargs.get("aimAxis", "x"), upAxis=kwargs.get("upAxis", "y"))
        case.assertSequenceAlmostEqual(back, angles, places=6)


def _expect_dot(case, call):
    a, b = _mq(call.target), call.kwargs["other"]
    case.assertAlmostEqual(call.result, a.x * b.x + a.y * b.y + a.z * b.z + a.w * b.w, places=12)


def _expect_rotate_vector(case, call):
    expected = _mv(call.kwargs["vector"]).rotateBy(_mq(call.target).normal())
    case.assertIs(type(call.result), Vector)
    case.assertSequenceAlmostEqual(call.result, expected)


def _expect_angle_to(case, call):
    a, b = _mq(call.target).normal(), _mq(call.kwargs["other"]).normal()
    expected = 2.0 * math.acos(min(1.0, abs(a.x * b.x + a.y * b.y + a.z * b.z + a.w * b.w)))
    case.assertAlmostEqual(call.result, expected, places=6)


def _expect_slerp(case, call):
    kwargs = call.kwargs
    expected = om2.MQuaternion.slerp(_mq(call.target).normal(), _mq(kwargs["other"]).normal(), kwargs["t"], kwargs.get("spin", 0))
    case.assertSequenceAlmostEqual(_value(case, call.result), _value(case, expected))


def _expect_swing_twist(case, call):
    """twist は軸の周りだけの回転で、twist を先に当てて swing を当てると元の回転になる(om2 の積)。"""
    swing, twist = call.result
    axis = _mv(call.kwargs.get("axis", (1.0, 0.0, 0.0))).normal()
    case.assertAlmostEqual((om2.MVector(twist.x, twist.y, twist.z) ^ axis).length(), 0.0, places=9)
    _assert_rotation(case, _mq(twist) * _mq(swing), call.target)


def _expect_as_roll_bend(case, call):
    kwargs = call.kwargs
    unit = _unit(kwargs)
    back = Quaternion.fromRollBend(*call.result, aimAxis=kwargs.get("aimAxis", "x"), upAxis=kwargs.get("upAxis", "y"), unit=unit)
    _assert_rotation(case, back, call.target)


def _expect_decomposed(case, call):
    order = call.kwargs.get("order", "xyz")
    index = order if isinstance(order, int) else ["xyz", "yzx", "zxy", "xzy", "yxz", "zyx"].index(order.lower())
    expected = om2.MEulerRotation.decompose(_mq(call.target).normal().asMatrix(), index)
    case.assertIsInstance(call.result, EulerRotate)
    case.assertEqual(call.result.order, index)
    case.assertSequenceAlmostEqual([call.result.x, call.result.y, call.result.z], [expected.x, expected.y, expected.z])


def _expect_mirror(case, call):
    """回転のマトリクスの、軸以外の列の符号を変えた回転(om2 の対角マトリクスとの積)と同じ。"""
    axis = call.kwargs.get("axis", "x")
    index = axis if isinstance(axis, int) else {"x": 0, "yz": 0, "zy": 0, "y": 1, "xz": 1, "zx": 1, "z": 2, "xy": 2, "yx": 2}[axis.lower()]
    flip = om2.MMatrix()
    for column in range(3):
        flip.setElement(column, column, 1.0 if column == index else -1.0)
    expected = om2.MTransformationMatrix(_mq(call.target).normal().asMatrix() * flip).rotation(asQuaternion=True)
    case.assertIs(type(call.result), type(call.target))
    _assert_rotation(case, call.result, expected)


#: 本体との食い違い(findings4/sweep-common-json-maths.md の M9)。
KNOWN_OTHER = _known("other", OTHER_INVALID[1:], "Raises に無い AttributeError(x・y・z・w を持たない値)")
KNOWN_XYZ = _known("vector", XYZ_INVALID[3:], "Raises に無い TypeError(3成分の並びでない値)")
KNOWN_SLERP = {
    **KNOWN_OTHER,
    **_known("t", ("a", None), "Raises に無い TypeError(om2 の slerp が MQuaternion expected と報告する)"),
    **_known("spin", (1.5, "a", None), "Raises に無い TypeError(om2 の slerp が MQuaternion expected と報告する)"),
    "invalid:t=nan": "NaN を受け付け、NaN のクォータニオンを返す",
}

METHODS = (
    Method(
        "fromAxisAngle",
        _classes,
        args=((0.0, 1.0, 0.0), 0.5),
        values={"axis": XYZ, "angle": (0.0, 0.5, -1.5, math.pi, 90, 720.0), "unit": UNITS},
        replace=("axis", "angle", "unit"),
        invalid={"axis": XYZ_INVALID, "angle": ("a", None, float("nan"), float("inf")), "unit": UNIT_INVALID},
        expect=_expect_axis_angle,
        writes=False,
        known={"invalid:angle=nan": "NaN を受け付け、NaN のクォータニオンを返す(fromRollBend は ValueError)"},
    ),
    Method(
        "fromRollBend",
        _classes,
        args=(0.1, 0.2, 0.3),
        values={"roll": (0.0, 0.5, -1.0, 90), "bendH": (0.0, 0.3, -0.7, 45), "bendV": (0.0, 0.4, -0.2, -30), "aimAxis": AXES, "upAxis": AXES, "unit": UNITS},
        replace=("roll", "bendH", "bendV", "aimAxis", "upAxis", "unit"),
        invalid={
            "roll": ("a", None, float("nan"), float("inf")),
            "bendH": ("a", None, float("nan")),
            "bendV": ("a", None, float("inf")),
            "aimAxis": ("w", "y", 0, None),
            "upAxis": ("w", "x", "-x", 1, None),
            "unit": UNIT_INVALID,
        },
        expect=_expect_roll_bend,
        writes=False,
    ),
    Method(
        "dot",
        _rotation,
        args=(om2.MQuaternion(),),
        values={"other": OTHERS},
        replace=("other",),
        invalid={"other": OTHER_INVALID[1:]},
        expect=_expect_dot,
        state=_value,
        writes=False,
        known=KNOWN_OTHER,
    ),
    Method(
        "rotateVector",
        _rotation,
        args=((1.0, 0.0, 0.0),),
        values={"vector": XYZ},
        replace=("vector",),
        invalid={"vector": XYZ_INVALID[1:]},
        expect=_expect_rotate_vector,
        state=_value,
        writes=False,
        known=KNOWN_XYZ,
    ),
    Method(
        "angleTo",
        _rotation,
        args=(om2.MQuaternion(),),
        values={"other": OTHERS},
        replace=("other",),
        invalid={"other": OTHER_INVALID},
        expect=_expect_angle_to,
        state=_value,
        writes=False,
        known=KNOWN_OTHER,
    ),
    Method(
        "slerp",
        _rotation,
        args=(om2.MQuaternion(), 0.5),
        values={"other": OTHERS, "t": (0.0, 0.25, 0.5, 1.0, -0.5, 1.5), "spin": (0, 1, -1)},
        replace=("other", "t", "spin"),
        invalid={"other": OTHER_INVALID, "t": ("a", None, float("nan")), "spin": (1.5, "a", None)},
        expect=_expect_slerp,
        state=_value,
        writes=False,
        known=KNOWN_SLERP,
    ),
    Method(
        "asSwingTwist",
        _rotation,
        values={"axis": XYZ},
        replace=("axis",),
        invalid={"axis": XYZ_INVALID},
        expect=_expect_swing_twist,
        state=_value,
        writes=False,
        known=_known("axis", XYZ_INVALID[3:], "Raises に無い TypeError(3成分の並びでない値)"),
    ),
    Method(
        "asRollBend",
        _rotation,
        values={"aimAxis": AXES, "upAxis": AXES, "unit": UNITS},
        replace=("aimAxis", "upAxis", "unit"),
        invalid={"aimAxis": ("w", "y", 0, None), "upAxis": ("w", "x", "-x", 1, None), "unit": UNIT_INVALID},
        expect=_expect_as_roll_bend,
        state=_value,
        writes=False,
    ),
    Method(
        "asDecomposedEulerRotate",
        _rotation,
        values={"order": ORDERS},
        replace=("order",),
        invalid={"order": ("xxy", "", 6, -1, True, 1.5, None)},
        expect=_expect_decomposed,
        state=_value,
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
)


class QuaternionArgumentSweepTest(ArgumentSweepCase):
    """Quaternionの公開メソッドの引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
