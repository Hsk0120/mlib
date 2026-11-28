"""Quaternionの公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

結果は om2 の同じ計算(``MQuaternion`` の作成・slerp・回転、``MEulerRotation.decompose``)と突き合わせる。
数学型はシーンを変えないので、Undo・fast の性質は当てはまらない(表は ``writes=False`` にし、
状態は対象の4成分にして、メソッドが自身を変えないことを確かめる)。
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

from mlib.maths import EulerRotate, Matrix, Quaternion, Vector


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
    """unit の指定。None は既定と同じラジアン。"""
    unit = kwargs.get("unit", "rad")
    return "rad" if unit is None else unit


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


def _scaled(case):
    """長さが1でないクォータニオン(正規化・長さ・逆の行に使う)。"""
    return Quaternion(0.2, 0.4, 0.1, 2.0)


def _negative(case):
    """w が負の単位クォータニオン(符号をそろえる行に使う)。"""
    return Quaternion(om2.MQuaternion(-0.1, -0.2, -0.3, -0.9).normal())


def _parts(value):
    """om2・mlib の値を、比べられる数の並びにする。"""
    if isinstance(value, om2.MQuaternion):
        return [value.x, value.y, value.z, value.w]
    if isinstance(value, om2.MEulerRotation):
        return [value.x, value.y, value.z, value.order]
    if isinstance(value, tuple):
        return [_parts(item) for item in value]
    return value if isinstance(value, float) else list(value)


_SAMPLE_MATRIX = Matrix(translate=(1.0, 2.0, 3.0), rotate=(0.1, 0.2, 0.3), scale=(1.0, 2.0, 3.0))
#: コンストラクターの位置引数の候補(なし・4成分・並び・コピー・角度と軸・2つの方向・オイラー回転・マトリクス)。
INIT_ARGS = (
    (),
    (0.1, 0.2, 0.3, 0.9),
    ((0.0, 0.7071, 0.0, 0.7071),),
    ([0, 0, 0, 1],),
    (om2.MQuaternion(0.2, 0.4, 0.1, 2.0),),
    (Quaternion(-0.1, -0.2, -0.3, -0.9),),
    (0.7, om2.MVector(1.0, 2.0, 0.5)),
    (om2.MVector(1.0, 0.0, 0.0), om2.MVector(0.0, 1.0, 0.0)),
    (om2.MVector(1.0, 0.0, 0.0), Vector(0.0, 1.0, 1.0), 0.5),
    (om2.MEulerRotation(0.1, 0.2, 0.3, om2.MEulerRotation.kYZX),),
    (EulerRotate(0.3, 0.2, 0.1, order="zxy"),),
    (om2.MMatrix(_SAMPLE_MATRIX),),
    (_SAMPLE_MATRIX,),
)
#: コンストラクターのキーワード引数の候補。
INIT_KWARGS = ({}, {"w": 0.5}, {"x": 0.5, "y": -0.5}, {"x": 0, "y": 1, "z": 0, "w": 0})
#: コンストラクターの誤った位置引数(成分が数でない・成分の数が多い)と、誤ったキーワード引数(知らない名前・数でない成分)。
INIT_ARGS_INVALID = (("a", 0.0, 0.0, 1.0), ("abc",), (None,), (1.0, 2.0, 3.0, 4.0, 5.0), (object(),))
INIT_KWARGS_INVALID = ({"v": 1.0}, {"x": "a"})
#: squad の両端と制御点(単位クォータニオン)。
_P = om2.MQuaternion()
_A = om2.MQuaternion(0.3, om2.MVector(1.0, 0.0, 0.0))
_B = om2.MQuaternion(0.8, om2.MVector(0.0, 1.0, 0.0))
_Q = om2.MQuaternion(1.2, om2.MVector(0.0, 1.0, 1.0))
SQUADS = ((_P, _A, _B, _Q, 0.5), (_P, _A, _B, _Q, 0.0), (Quaternion(_P), Quaternion(_A), Quaternion(_B), Quaternion(_Q), 0.25), (_P, _A, _B, _Q, 0.75, 1))
SQUAD_POINTS = ((_P, _A, _Q), (Quaternion(_A), Quaternion(_B), Quaternion(_Q)), (_Q, _B, _P))
#: 0のクォータニオンで ValueError になる行の指定。
ZERO = (ErrorState("0のクォータニオン", lambda case, target: Quaternion(0.0, 0.0, 0.0, 0.0), ValueError),)


def _expect_init(case, call):
    """キーワードが無ければ om2 の同じ計算、あれば位置引数の続きをキーワードで埋めた成分と同じ。"""
    args, kwargs = call.kwargs.get("args", ()), call.kwargs.get("kwargs", {})
    case.assertIs(type(call.result), Quaternion)
    if kwargs:
        if not all(_is_number(value) for value in args):
            return
        filled = dict(zip("xyzw", args), **kwargs)
        expected = [filled.get(name, default) for name, default in zip("xyzw", (0.0, 0.0, 0.0, 1.0))]
    elif len(args) == 1 and isinstance(args[0], om2.MEulerRotation):
        expected = _parts(om2.MEulerRotation.asQuaternion(args[0]))
    elif len(args) == 1 and isinstance(args[0], om2.MMatrix):
        expected = _parts(om2.MTransformationMatrix(om2.MMatrix(args[0])).rotation(asQuaternion=True))
    else:
        expected = _parts(om2.MQuaternion(*args))
    case.assertSequenceAlmostEqual(_parts(call.result), expected)


def _same_as(name, kind=Quaternion, static=False):
    """om2.MQuaternion の同じ名前のメソッドを同じ引数で呼んだ結果と同じで、戻り値は kind の型(static は静的メソッド)。"""

    def expect(case, call):
        args = call.kwargs.get("args", ())
        function = getattr(om2.MQuaternion, name)
        expected = function(*args) if static else function(_mq(call.target), *args)
        if isinstance(kind, tuple):
            case.assertEqual(tuple(type(item) for item in call.result), kind)
        else:
            case.assertIs(type(call.result), kind)
        case.assertTrue(same(_parts(call.result), _parts(expected), 9), f"om2.MQuaternion.{name} と違う: {call.result!r} と {expected!r}")

    return expect


def _expect_length(case, call):
    q = call.target
    case.assertAlmostEqual(call.result, math.sqrt(q.x * q.x + q.y * q.y + q.z * q.z + q.w * q.w), places=12)


def _expect_length_sq(case, call):
    q = call.target
    case.assertAlmostEqual(call.result, q.x * q.x + q.y * q.y + q.z * q.z + q.w * q.w, places=12)


def _expect_canonical(case, call):
    """軸は長さ1・角度は0〜piで、om2 で軸と角度から作り直すと同じ回転になる。"""
    axis, angle = call.result
    case.assertIs(type(axis), Vector)
    case.assertAlmostEqual(om2.MVector(axis).length(), 1.0, places=9)
    case.assertTrue(0.0 <= angle <= math.pi)
    _assert_rotation(case, om2.MQuaternion(angle, om2.MVector(axis)), call.target)


def _expect_unit_matrix(case, call):
    case.assertIs(type(call.result), Matrix)
    case.assertSequenceAlmostEqual(list(call.result), list(_mq(call.target).normal().asMatrix()))


def _expect_safe_log(case, call):
    """w が負なら符号を反転してから、om2 の log を呼んだ値と同じ。"""
    source = _mq(call.target)
    if source.w < 0.0:
        source.negateIt()
    case.assertIs(type(call.result), Quaternion)
    case.assertSequenceAlmostEqual(_parts(call.result), _parts(source.log()))


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
    Method(
        "__init__",
        _rotation,
        function=_constructor(Quaternion),
        values={"*": INIT_ARGS, "**": INIT_KWARGS},
        invalid={"*": INIT_ARGS_INVALID, "**": INIT_KWARGS_INVALID},
        expect=_expect_init,
        state=_value,
        writes=False,
    ),
    Method("squad", _rotation, args=SQUADS[0], values={"*": SQUADS}, expect=_same_as("squad", static=True), state=_value, writes=False),
    Method("squadPt", _rotation, args=SQUAD_POINTS[0], values={"*": SQUAD_POINTS}, expect=_same_as("squadPt", static=True), state=_value, writes=False),
    Method("length", _scaled, expect=_expect_length, state=_value, writes=False),
    Method("lengthSq", _scaled, expect=_expect_length_sq, state=_value, writes=False),
    Method("unit", _scaled, expect=_same_as("normal"), state=_value, writes=False, errors=ZERO),
    Method("conjugate", _scaled, expect=_same_as("conjugate"), state=_value, writes=False),
    Method("inverse", _scaled, expect=_same_as("inverse"), state=_value, writes=False, errors=ZERO),
    Method("asCanonicalAxisAngle", _negative, expect=_expect_canonical, state=_value, writes=False, errors=ZERO),
    Method("asUnitMatrix", _scaled, expect=_expect_unit_matrix, state=_value, writes=False, errors=ZERO),
    Method("normal", _scaled, expect=_same_as("normal"), state=_value, writes=False),
    Method("exp", _rotation, expect=_same_as("exp"), state=_value, writes=False),
    Method("log", _rotation, expect=_same_as("log"), state=_value, writes=False),
    Method("safeLog", _negative, expect=_expect_safe_log, state=_value, writes=False),
    Method("asMatrix", _rotation, expect=_same_as("asMatrix", Matrix), state=_value, writes=False),
    Method("asEulerRotation", _rotation, expect=_same_as("asEulerRotation", EulerRotate), state=_value, writes=False),
    Method("asAxisAngle", _rotation, expect=_same_as("asAxisAngle", (Vector, float)), state=_value, writes=False),
)


class QuaternionArgumentSweepTest(ArgumentSweepCase):
    """Quaternionの公開メソッドの引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
