"""Matrixの公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

結果は om2 の同じ計算(``MTransformationMatrix`` の合成・分解、``MMatrix`` の積・``adjoint``・
``MQuaternion.slerp``)と突き合わせる。数学型はシーンを変えないので、Undo・fast の性質は当てはまらない
(表は ``writes=False`` にし、状態は対象の16成分にして、メソッドが自身を変えないことを確かめる)。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import inspect
import re
import sys
import unittest

import maya.api.OpenMaya as om2

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Method

from mlib.maths import EulerRotate, Matrix, Quaternion, Translate, Vector

K = om2.MSpace.kTransform


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
    """値の状態(16成分)。メソッドが自身を変えないことを確かめる。"""
    return list(target.values) if isinstance(target, Matrix) else None


def _om2_matrix(translate=(1.0, 2.0, 3.0), rotate=(0.1, 0.2, 0.3), scale=(1.0, 2.0, 3.0), shear=(0.0, 0.0, 0.0)):
    tm = om2.MTransformationMatrix()
    tm.setTranslation(om2.MVector(*translate), K)
    tm.setRotation(om2.MEulerRotation(*rotate))
    tm.setScale(scale, K)
    tm.setShear(shear, K)
    return tm.asMatrix()


def _matrix(case):
    return Matrix(list(_om2_matrix()))


def _classes(case):
    return _host("Matrix", compose=Matrix.compose, fromAxes=Matrix.fromAxes, fromAim=Matrix.fromAim)


def _flat(matrix):
    return [matrix.getElement(row, column) for row in range(4) for column in range(4)]


def _assert_matrix(case, actual, expected, places=6):
    case.assertSequenceAlmostEqual(_flat(om2.MMatrix(actual)), _flat(om2.MMatrix(expected)), places=places)


def _mv(value):
    if isinstance(value, om2.MPoint):
        return om2.MVector(value.x, value.y, value.z)
    return om2.MVector(*list(value)[:3])


#: 3成分の候補(タプル・リスト・om2 の型・mlib の型・負・0)。
XYZ = ((1.0, 2.0, 3.0), [0, 0, 0], om2.MVector(-1.0, 0.5, 4.0), om2.MPoint(2.0, -2.0, 2.0), Translate(0.5, 0.5, 0.5), (-3.0, 0.0, 7.5))
#: 回転の候補(XYZ のラジアン・EulerRotate・回転順序つきの om2 の Euler・クォータニオン)。
ROTATES = (
    (0.0, 0.0, 0.0),
    (0.1, -0.2, 0.3),
    EulerRotate(0.3, 0.2, 0.1, order="zxy"),
    om2.MEulerRotation(0.5, 0.0, 0.25, om2.MEulerRotation.kYZX),
    om2.MQuaternion(0.0, 0.0, 0.7071, 0.7071),
    Quaternion(0.1, 0.2, 0.3, 0.9),
)
#: 3成分の誤った値(成分の数・成分の型・並びでない値)。
XYZ_INVALID = ((1.0, 2.0), (1.0, 2.0, 3.0, 4.0), "abc", None, 1.0, (float("nan"), 0.0, 0.0), (True, 0.0, 0.0), object())
#: 軸の名前。
AXES = ("x", "y", "z", "-x", "-y", "-z")
#: 相手のマトリクスの候補(om2・mlib・16成分の並び・4行4列・単位)。
OTHERS = (
    om2.MMatrix(_om2_matrix((0.0, 0.0, 0.0), (0.4, 0.0, 0.0), (1.0, 1.0, 1.0))),
    Matrix(),
    list(_om2_matrix((5.0, 0.0, 0.0))),
    [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [1, 2, 3, 1]],
)
#: 相手のマトリクスの誤った値。
MATRIX_INVALID = (list(range(15)), "abc", None, 1.0, object())


def _expect_compose(case, call):
    kwargs = call.kwargs
    tm = om2.MTransformationMatrix()
    tm.setTranslation(_mv(kwargs.get("translate", (0.0, 0.0, 0.0))), K)
    rotate = kwargs.get("rotate", (0.0, 0.0, 0.0))
    if isinstance(rotate, om2.MQuaternion):
        tm.setRotation(om2.MQuaternion(rotate).normal())
    elif isinstance(rotate, om2.MEulerRotation):
        tm.setRotation(om2.MEulerRotation(rotate.x, rotate.y, rotate.z, rotate.order))
    else:
        tm.setRotation(om2.MEulerRotation(*rotate))
    tm.setScale(list(kwargs.get("scale", (1.0, 1.0, 1.0)))[:3], K)
    tm.setShear(list(kwargs.get("shear", (0.0, 0.0, 0.0)))[:3], K)
    case.assertIsInstance(call.result, Matrix)
    _assert_matrix(case, call.result, tm.asMatrix(), places=4)


def _expect_from_axes(case, call):
    rows = [_mv(call.kwargs[name]) for name in ("x", "y", "z")] + [_mv(call.kwargs.get("position", (0.0, 0.0, 0.0)))]
    expected = om2.MMatrix([[row.x, row.y, row.z, 1.0 if index == 3 else 0.0] for index, row in enumerate(rows)])
    _assert_matrix(case, call.result, expected)


def _expect_from_aim(case, call):
    """aimAxis の行が aim の向き、upAxis の行が aim に直交する up の向きで、右手系の正規直交になる。"""
    result, kwargs = call.result, call.kwargs
    aim = _mv(kwargs["aim"]).normal()
    up = _mv(kwargs["up"])
    up = (up - aim * (up * aim)).normal()
    case.assertSequenceAlmostEqual(result.getAxis(kwargs.get("aimAxis", "x")), aim)
    case.assertSequenceAlmostEqual(result.getAxis(kwargs.get("upAxis", "y")), up)
    case.assertAlmostEqual(om2.MMatrix(result).det3x3(), 1.0, places=6)
    case.assertSequenceAlmostEqual(_flat(om2.MMatrix(result))[12:15], list(_mv(kwargs.get("position", (0.0, 0.0, 0.0)))))


def _expect_axis(case, call):
    axis = call.kwargs.get("axis", "x")
    index = axis if isinstance(axis, int) else "xyz".index(axis[-1])
    sign = -1.0 if isinstance(axis, str) and axis.startswith("-") else 1.0
    expected = [om2.MMatrix(call.target).getElement(index, column) * sign for column in range(3)]
    case.assertIsInstance(call.result, Vector)
    case.assertSequenceAlmostEqual(call.result, expected)


def _expect_extract(case, call):
    source = om2.MMatrix(call.target)
    tm = om2.MTransformationMatrix(source)
    part = call.kwargs["part"]
    if part == "translate":
        expected = om2.MMatrix()
        for column in range(3):
            expected.setElement(3, column, source.getElement(3, column))
    elif part == "3x3":
        expected = om2.MMatrix()
        for row in range(3):
            for column in range(3):
                expected.setElement(row, column, source.getElement(row, column))
    elif part == "rotate":
        expected = tm.rotation(asQuaternion=True).asMatrix()
    else:
        scaled = om2.MTransformationMatrix()
        scaled.setScale(tm.scale(K), K)
        scaled.setShear(tm.shear(K), K)
        expected = scaled.asMatrix()
    case.assertIs(type(call.result), type(call.target))
    _assert_matrix(case, call.result, expected)


def _expect_equivalent(case, call):
    other = call.kwargs["other"]
    other = om2.MMatrix(other if isinstance(other, om2.MMatrix) else Matrix(other))
    case.assertIs(call.result, om2.MMatrix(call.target).isEquivalent(other, call.kwargs.get("tolerance", 1e-10)))


def _expect_identity(case, call):
    tolerance = call.kwargs.get("tolerance", 1e-10)
    case.assertIs(call.result, all(abs(a - b) <= tolerance for a, b in zip(_flat(om2.MMatrix(call.target)), _flat(om2.MMatrix()))))


def _expect_non_uniform(case, call):
    tm = om2.MTransformationMatrix(om2.MMatrix(call.target))
    scale = [abs(value) for value in tm.scale(K)]
    tolerance = call.kwargs.get("tolerance", 1e-10)
    expected = any(abs(value) > tolerance for value in tm.shear(K)) or max(scale) - min(scale) > tolerance
    case.assertIs(call.result, expected)


def _expect_blend(case, call):
    other = call.kwargs["other"]
    other = om2.MMatrix(other if isinstance(other, om2.MMatrix) else Matrix(other))
    weight = call.kwargs["weight"]
    start, end = om2.MTransformationMatrix(om2.MMatrix(call.target)), om2.MTransformationMatrix(other)
    tm = om2.MTransformationMatrix()
    tm.setTranslation(start.translation(K) + (end.translation(K) - start.translation(K)) * weight, K)
    tm.setRotation(om2.MQuaternion.slerp(start.rotation(asQuaternion=True), end.rotation(asQuaternion=True), weight))
    tm.setScale([a + (b - a) * weight for a, b in zip(start.scale(K), end.scale(K))], K)
    tm.setShear([a + (b - a) * weight for a, b in zip(start.shear(K), end.shear(K))], K)
    _assert_matrix(case, call.result, tm.asMatrix(), places=5)


def _expect_point(case, call):
    point = om2.MPoint(_mv(call.kwargs["value"])) * om2.MMatrix(call.target)
    case.assertIsInstance(call.result, Translate)
    case.assertSequenceAlmostEqual(call.result, [point.x, point.y, point.z])


def _expect_vector(case, call):
    vector = _mv(call.kwargs["value"]) * om2.MMatrix(call.target)
    case.assertIs(type(call.result), Vector)
    case.assertSequenceAlmostEqual(call.result, vector)


def _expect_mirror(case, call):
    """3x3 は軸以外の列の符号を変え(om2 の対角マトリクスとの積)、平行移動は中心で反転する。"""
    axis = call.kwargs.get("axis", "x")
    index = axis if isinstance(axis, int) else {"x": 0, "yz": 0, "zy": 0, "y": 1, "xz": 1, "zx": 1, "z": 2, "xy": 2, "yx": 2}[axis.lower()]
    pivot = list(call.kwargs.get("pivot", (0.0, 0.0, 0.0)))[:3]
    flip = om2.MMatrix()
    for column in range(3):
        flip.setElement(column, column, 1.0 if column == index else -1.0)
    expected = om2.MMatrix(call.target) * flip
    for column in range(3):
        expected.setElement(3, column, om2.MMatrix(call.target).getElement(3, column))
    expected.setElement(3, index, 2 * pivot[index] - expected.getElement(3, index))
    case.assertIs(type(call.result), type(call.target))
    _assert_matrix(case, call.result, expected)


def _expect_cofactor(case, call):
    """余因子は om2 の adjoint の転置の要素と同じ。"""
    row, column = call.kwargs["row"] % 4, call.kwargs["column"] % 4
    case.assertAlmostEqual(call.result, om2.MMatrix(call.target).adjoint().getElement(column, row), places=6)


TOLERANCE_INVALID = {"tolerance": ("a", None, float("nan"), float("inf"), -1.0, True)}


def _known(name, values, reason):
    """段2の場合の名前を、fnmatch の記号([ など)を文字として扱う形にして返す。"""
    return {"invalid:" + re.sub(r"([*?[])", r"[\1]", f"{name}={value!r}"): reason for value in values}


#: 本体との食い違い(findings4/sweep-common-json-maths.md の M3〜M7)。
_COMPOSE_TYPE = "Raises に無い TypeError(3成分の並びでない値)"
_COMPOSE_ACCEPT = "None・NaN・bool の成分を受け付ける"
KNOWN_COMPOSE = {}
for _name in ("translate", "rotate", "scale", "shear"):
    KNOWN_COMPOSE.update(_known(_name, (XYZ_INVALID[4], XYZ_INVALID[7]), _COMPOSE_TYPE))
    KNOWN_COMPOSE.update(_known(_name, (None, XYZ_INVALID[5], XYZ_INVALID[6]), _COMPOSE_ACCEPT))
    if _name != "rotate":
        KNOWN_COMPOSE.update(_known(_name, ("abc",), _COMPOSE_TYPE))
KNOWN_EQUIVALENT = {
    **_known("other", (MATRIX_INVALID[0], "abc", 1.0, MATRIX_INVALID[4]), "Raises に無い ValueError(マトリクスにできない値)"),
    "invalid:other=None": "None を単位マトリクスとして受け付ける",
    **_known("tolerance", ("a", None), "Raises に無い TypeError(om2 へそのまま渡す)"),
    "invalid:tolerance=-1.0": "負の tolerance を受け付ける",
}
KNOWN_TRANSFORM = _known("value", XYZ_INVALID[:5], "Raises が無いのに TypeError・ValueError になる(3成分にできない値)")

METHODS = (
    Method(
        "compose",
        _classes,
        values={
            "translate": XYZ,
            "rotate": ROTATES,
            "scale": ((1.0, 1.0, 1.0), (2.0, 0.5, -1.0), om2.MVector(3.0, 3.0, 3.0)),
            "shear": ((0.0, 0.0, 0.0), (0.1, 0.2, 0.3)),
        },
        replace=("translate", "rotate", "scale", "shear"),
        invalid={"translate": XYZ_INVALID, "rotate": (*XYZ_INVALID, om2.MQuaternion(0.0, 0.0, 0.0, 0.0)), "scale": XYZ_INVALID, "shear": XYZ_INVALID},
        expect=_expect_compose,
        writes=False,
        known=KNOWN_COMPOSE,
    ),
    Method(
        "fromAxes",
        _classes,
        args=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        values={"x": XYZ, "y": XYZ, "z": XYZ, "position": XYZ},
        replace=("x", "y", "z", "position"),
        invalid={"x": XYZ_INVALID, "y": XYZ_INVALID, "z": XYZ_INVALID, "position": XYZ_INVALID},
        expect=_expect_from_axes,
        writes=False,
    ),
    Method(
        "fromAim",
        _classes,
        args=((1.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        values={
            "aim": ((1.0, 1.0, 0.0), [0, 0, -2], om2.MVector(0.3, -1.0, 0.2), om2.MPoint(5.0, 0.0, 0.0)),
            "up": ((0.0, 0.0, 1.0), [0, 1, 0.5], om2.MPoint(0.0, 1.0, 1.0), om2.MVector(0.0, 1.0, 1.0)),
            "aimAxis": AXES,
            "upAxis": AXES,
            "position": XYZ,
        },
        replace=("aim", "up", "aimAxis", "upAxis", "position"),
        invalid={
            "aim": (*XYZ_INVALID, (0.0, 0.0, 0.0), (0.0, 0.0, 5.0)),
            "up": (*XYZ_INVALID, (0.0, 0.0, 0.0), (-2.0, -2.0, 0.0)),
            "aimAxis": ("w", "y", "", 0, None),
            "upAxis": ("w", "x", "-x", 1, None),
            "position": XYZ_INVALID,
        },
        expect=_expect_from_aim,
        writes=False,
    ),
    Method(
        "getAxis",
        _matrix,
        values={"axis": (*AXES, 0, 1, 2)},
        replace=("axis",),
        invalid={"axis": ("w", "xy", 3, -1, True, 1.5, None)},
        expect=_expect_axis,
        state=_value,
        writes=False,
    ),
    Method(
        "extract",
        _matrix,
        args=("translate",),
        values={"part": ("translate", "rotate", "scale", "3x3")},
        replace=("part",),
        invalid={"part": ("Translate", "shear", "", 1, None)},
        expect=_expect_extract,
        state=_value,
        writes=False,
    ),
    Method(
        "isEquivalent",
        _matrix,
        args=(Matrix(),),
        values={"other": (*OTHERS, _om2_matrix()), "tolerance": (0.0, 1e-10, 0.5, 100.0)},
        replace=("other", "tolerance"),
        invalid={"other": MATRIX_INVALID, "tolerance": ("a", None, -1.0)},
        expect=_expect_equivalent,
        state=_value,
        writes=False,
        known=KNOWN_EQUIVALENT,
    ),
    Method(
        "isIdentity",
        _matrix,
        values={"tolerance": (0.0, 1e-10, 2.9, 3.1, 1000.0)},
        replace=("tolerance",),
        invalid=TOLERANCE_INVALID,
        expect=_expect_identity,
        state=_value,
        writes=False,
    ),
    Method(
        "hasNonUniformScale",
        _matrix,
        values={"tolerance": (0.0, 1e-10, 1.9, 2.1, 1000.0)},
        replace=("tolerance",),
        invalid=TOLERANCE_INVALID,
        expect=_expect_non_uniform,
        state=_value,
        writes=False,
    ),
    Method(
        "blend",
        _matrix,
        args=(Matrix(), 0.5),
        values={"other": OTHERS, "weight": (0.0, 0.25, 0.5, 1.0, 0, 1)},
        replace=("other", "weight"),
        invalid={"other": (*MATRIX_INVALID, om2.MMatrix([[0] * 4] * 4)), "weight": (-0.1, 1.5, "a", None, True, float("nan"), float("inf"))},
        expect=_expect_blend,
        state=_value,
        writes=False,
        known={"invalid:other=None": "None を単位マトリクスとして受け付ける"},
    ),
    Method(
        "transformPoint",
        _matrix,
        args=((1.0, 0.0, 0.0),),
        values={"value": XYZ},
        replace=("value",),
        invalid={"value": XYZ_INVALID[:5]},
        expect=_expect_point,
        state=_value,
        writes=False,
        known=KNOWN_TRANSFORM,
    ),
    Method(
        "transformVector",
        _matrix,
        args=((1.0, 0.0, 0.0),),
        values={"value": XYZ},
        replace=("value",),
        invalid={"value": XYZ_INVALID[:5]},
        expect=_expect_vector,
        state=_value,
        writes=False,
        known=KNOWN_TRANSFORM,
    ),
    Method(
        "mirror",
        _matrix,
        values={"axis": ("x", "y", "z", "YZ", "XZ", "XY", "zx", 0, 1, 2), "pivot": XYZ},
        replace=("axis", "pivot"),
        invalid={"axis": ("w", "xyz", "", 3, -1, 1.5, None, True), "pivot": XYZ_INVALID[:5]},
        expect=_expect_mirror,
        state=_value,
        writes=False,
    ),
    Method(
        "cofactor",
        _matrix,
        args=(0, 0),
        values={"row": (0, 1, 2, 3, -1, -4), "column": (0, 1, 2, 3, -1, -4)},
        replace=("row", "column"),
        invalid={"row": (4, -5, 1.5, "a", None, True), "column": (4, -5, 1.5, "a", None, True)},
        expect=_expect_cofactor,
        state=_value,
        writes=False,
        known={"invalid:row=True": "bool を番号として受け付ける", "invalid:column=True": "bool を番号として受け付ける"},
    ),
)


class MatrixArgumentSweepTest(ArgumentSweepCase):
    """Matrixの公開メソッドの引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
