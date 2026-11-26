"""NurbsCurveのメソッドの引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
点の読み書きと反転(getPoints・setPoints・mirror)は ``test_controlPointShape_argumentSweep.py`` で確かめる。
"""

import math
import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Lazy, Method, RoundTrip

from mlib.maths import Matrix, Vector

#: 開いた次数3のカーブのCV(xy平面の波形)。
POINTS = ((0.0, 0.0, 0.0), (1.0, 2.0, 0.0), (2.0, 0.0, 0.0), (3.0, -2.0, 0.0), (4.0, 0.0, 0.0), (5.0, 2.0, 0.0), (6.0, 0.0, 0.0))
#: 両端が最大多重度で、内側の2に重複ノットがあるノット(範囲は0〜3)。
KNOTS = (0.0, 0.0, 0.0, 1.0, 2.0, 2.0, 3.0, 3.0, 3.0)
#: 両端が最大多重度でない、均等なノット(makeMultipleEndKnots の確かめ用)。
UNIFORM_KNOTS = (0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0)
#: 距離の単位と、cmからの係数。
UNIT_FACTORS = {
    "cm": 1.0,
    "mm": 10.0,
    "m": 0.01,
    "km": 1e-5,
    "in": 1 / 2.54,
    "ft": 1 / 30.48,
    "yd": 1 / 91.44,
    "mi": 1 / 160934.4,
    "millimeter": 10.0,
    None: 1.0,
}
#: ワールド空間の長い名前と短縮名(同時に指定できない)。
SPACE = ("worldSpace", "ws")
#: 軸の名前。
AXES = ("x", "y", "z", "-x", "-y", "-z")


def _place(case, transform):
    """トランスフォームを動かし、均等に2倍する(ワールド空間の値はローカルの2倍の長さになる)。"""
    cmds.setAttr(transform + ".translate", 1.0, 2.0, 3.0)
    cmds.setAttr(transform + ".scale", 2.0, 2.0, 2.0)
    # cmds.curve・cmds.circle はシェイプを名前空間の外に作るので、名前空間の中へ移す。
    for shape in cmds.listRelatives(transform, shapes=True, fullPath=True) or []:
        cmds.rename(shape, case.name("curveShape#"))
    return mlib.getNode(transform).getShape()


def _make_curve(case, knots=KNOTS):
    """POINTS・KNOTS の開いた次数3のカーブを作り、シェイプを返す。"""
    return _place(case, cmds.curve(name=case.name("curve#"), degree=3, point=POINTS, knot=knots))


def _make_uniform(case):
    return _make_curve(case, UNIFORM_KNOTS)


def _make_circle(case):
    """閉じた平面の円(周期カーブ。末尾のCVが先頭と重なる)を作り、シェイプを返す。"""
    return _place(case, cmds.circle(name=case.name("circle#"), normal=(0, 0, 1), radius=1.0, constructionHistory=False)[0])


def _make_curves(case):
    singles = [_make_curve(case), _make_curve(case)]
    return mlib.Nodes(singles), singles


def _shape_state(case, target):
    """sceneState に、名前空間のカーブのCV・ノット・次数・形式を足す。"""
    state = case.sceneState()
    for name in cmds.ls(case.ns + ":*", type="nurbsCurve", long=True) or []:
        fn = _fn(name)
        state.append((name, [tuple(point) for point in fn.cvPositions()], list(fn.knots()), fn.degree, fn.form))
    return state


def _fn(target):
    selection = om2.MSelectionList()
    selection.add(target if isinstance(target, str) else target.getName(full=True))
    return om2.MFnNurbsCurve(selection.getDagPath(0))


def _world(kwargs):
    return bool(kwargs.get("worldSpace", kwargs.get("ws", False)))


def _curve_point(param, offset=(0.0, 0.0, 0.0), kind=tuple):
    """カーブのパラメーターの位置(ローカル)を、呼ぶ直前に作る値。"""

    def make(case):
        point = _fn(cmds.ls(case.ns + ":*", type="nurbsCurve", long=True)[0]).getPointAtParam(param)
        return kind((point.x + offset[0], point.y + offset[1], point.z + offset[2]))

    return Lazy(make, f"<param{param}の点{'+' + str(offset) if any(offset) else ''}({kind.__name__})>")


def _mpoint(values):
    return om2.MPoint(*values)


def _mvector(values):
    return om2.MVector(*values)


#: カーブ上・カーブから離れた点(tuple・list・MPoint・MVector)。
POINT_VALUES = (
    _curve_point(1.5),
    _curve_point(0.5, kind=list),
    _curve_point(2.5, kind=_mpoint),
    _curve_point(1.0, kind=_mvector),
    _curve_point(1.5, offset=(0.0, 0.0, 1.0)),
)
#: 点の誤った値(成分の数・型・有限でない成分)。
POINT_INVALID = ((1.0, 2.0), (1.0, 2.0, 3.0, 4.0), "abc", None, object(), (float("nan"), 0.0, 0.0), (1.0, "a", 0.0))


# ----------------------------------------------------------------------
# expect


def _expect_cvs(case, call):
    """getCVs の結果を、番号から作った cmds の名前と比べる。"""
    shape = call.target.getName(full=True)
    indices = call.kwargs.get("indices")
    if indices is None:
        indices = range(_fn(shape).numCVs)
    elif isinstance(indices, int):
        indices = [indices]
    expected = set(cmds.ls([f"{shape}.cv[{index}]" for index in indices], long=True, flatten=True) or [])
    actual = set(cmds.ls(call.result, long=True, flatten=True) or []) if expected else set()
    case.assertEqual(actual, expected)


def _expect_mfn(case, call):
    case.assertIsInstance(call.result, om2.MFnNurbsCurve)
    case.assertEqual(call.result.numCVs, len(POINTS))


def _expect_num_cvs(case, call):
    case.assertEqual(call.result, len(cmds.ls(call.target.getName(full=True) + ".cv[*]", flatten=True)))


def _expect_knots(case, call):
    case.assertEqual(call.result, list(_fn(call.target).knots()))
    case.assertEqual(call.result, list(KNOTS))


def _expect_set_knots(case, call):
    case.assertIsNone(call.result)
    case.assertTrue(all(abs(a - b) < 1e-9 for a, b in zip(_fn(call.target).knots(), call.kwargs["knots"])))


def _expect_reduce(case, call):
    """重複ノット2が1つになる。"""
    case.assertIsNone(call.result)
    case.assertEqual(list(_fn(call.target).knots()).count(call.kwargs["parameter"]), 1)


def _expect_remove(case, call):
    case.assertIsNone(call.result)
    case.assertNotIn(call.kwargs["parameter"], list(_fn(call.target).knots()))


def _expect_end_knots(case, call):
    case.assertIsNone(call.result)
    knots = list(_fn(call.target).knots())
    case.assertEqual(knots[0], knots[2])
    case.assertEqual(knots[-1], knots[-3])


def _expect_length(case, call):
    """getLength を om2 の長さ(ワールドはローカルの2倍)と単位の係数で確かめる。"""
    fn = _fn(call.target)
    param = call.kwargs.get("param")
    local = 0.0
    if param is None:
        local = fn.length(call.kwargs.get("tolerance", 1e-6))
    elif param > fn.knotDomain[0]:
        local = fn.findLengthFromParam(param)
    expected = local * (2.0 if _world(call.kwargs) else 1.0) * UNIT_FACTORS[call.kwargs.get("distanceUnit", "cm")]
    # 許容誤差は、計算する空間(ワールドなら2倍の大きさ)の近似の誤差になる。
    case.assertAlmostEqual(call.result, expected, delta=max(1e-6, call.kwargs.get("tolerance", 0.0)) * max(1.0, expected))


def _expect_area(case, call):
    """半径1の円の面積はほぼπ、ワールド空間ではその4倍。"""
    expected = math.pi * (4.0 if _world(call.kwargs) else 1.0)
    case.assertAlmostEqual(call.result, expected, delta=0.02 * expected)


def _expect_rebuild(case, call):
    """次数・パラメーターの範囲が指定のとおりになる(スパンの数は Maya の結果に任せる)。"""
    case.assertIsNone(call.result)
    fn = _fn(call.target)
    degree = call.kwargs.get("degree")
    if degree is not None:
        case.assertEqual(fn.degree, degree)
    keep = call.kwargs.get("keepRange", "original")
    start, end = fn.knotDomain
    if keep == "unit":
        case.assertEqual((round(start, 9), round(end, 9)), (0.0, 1.0))
    elif keep == "spans":
        case.assertEqual((round(start, 9), round(end, 9)), (0.0, float(fn.numSpans)))
    else:
        case.assertEqual((round(start, 9), round(end, 9)), (0.0, 3.0))


def _expect_reverse(case, call):
    case.assertIsNone(call.result)
    points = _fn(call.target).cvPositions()
    case.assertSequenceAlmostEqual(list(points[0])[:3], POINTS[-1])
    case.assertSequenceAlmostEqual(list(points[-1])[:3], POINTS[0])


def _expect_collocated(case, call):
    """getCollocatedCVGroups を、CVどうしの距離から作ったグループと比べる(ワールドは2倍の距離)。"""
    positions = _fn(call.target).cvPositions()
    tolerance = call.kwargs.get("tolerance", 1e-6) / (2.0 if _world(call.kwargs) else 1.0)
    expected, assigned = [], set()
    for i in range(len(positions)):
        if i in assigned:
            continue
        group = [j for j in range(i, len(positions)) if j not in assigned and positions[i].distanceTo(positions[j]) <= tolerance]
        if len(group) > 1:
            assigned.update(group)
            expected.append(group)
    case.assertEqual(call.result, expected)


def _expect_range(case, call):
    shape = call.target.getName(full=True)
    case.assertEqual(call.result, (cmds.getAttr(shape + ".minValue"), cmds.getAttr(shape + ".maxValue")))


def _to_local(case, target, point, world):
    """ワールド空間の点を、シェイプのローカル空間の MPoint にする。"""
    point = om2.MPoint(*list(point)[:3])
    if not world:
        return point
    return point * target.mpath().inclusiveMatrixInverse()


def _expect_param(case, call):
    """point なら、そのパラメーターの位置が点と同じ。length なら om2 の findParamFromLength と同じ。"""
    fn = _fn(call.target)
    world = _world(call.kwargs)
    point = call.kwargs.get("point")
    if point is not None:
        found = fn.getPointAtParam(call.result)
        case.assertLess(found.distanceTo(_to_local(case, call.target, point, world)), 1e-4)
        return
    factor = UNIT_FACTORS[call.kwargs.get("distanceUnit", "cm")] * (2.0 if world else 1.0)
    case.assertAlmostEqual(call.result, fn.findParamFromLength(call.kwargs["length"] / factor), places=4)


def _expect_on_curve(case, call):
    if _world(call.kwargs):
        return
    point = om2.MPoint(*list(call.kwargs["point"])[:3])
    case.assertEqual(call.result, _fn(call.target).isPointOnCurve(point, call.kwargs.get("tolerance", 1e-7)))


def _expect_closest(case, call):
    world = _world(call.kwargs)
    found, param = _fn(call.target).closestPoint(_to_local(case, call.target, call.kwargs["point"], world), tolerance=1e-7)
    case.assertAlmostEqual(call.result[1], param, places=5)
    if not world:
        case.assertSequenceAlmostEqual(call.result[0], list(found)[:3], places=5)


def _expect_at_param(case, call):
    """getAtParam のローカル空間の値を om2 と比べる(ワールドは型と長さだけ)。"""
    what = call.kwargs.get("what", "point")
    result = call.result
    if what == "derivatives":
        case.assertEqual(len(result), 3 if call.kwargs.get("secondOrder") else 2)
        return
    case.assertIsInstance(result, Vector)
    if what in ("tangent", "normal"):
        case.assertAlmostEqual(result.length(), 1.0, places=6)
    if _world(call.kwargs):
        return
    fn = _fn(call.target)
    param = call.kwargs["param"]
    if what == "point":
        case.assertSequenceAlmostEqual(result, list(fn.getPointAtParam(param))[:3], places=6)
    elif what == "tangent":
        case.assertSequenceAlmostEqual(result, list(fn.tangent(param).normal()), places=6)


def _expect_params_along(case, call):
    """count 個で、始点から等しい長さの間隔に並ぶ(ワールドでも均等スケールなので同じ)。"""
    count = call.kwargs["count"]
    fn = _fn(call.target)
    case.assertEqual(len(call.result), count)
    case.assertAlmostEqual(call.result[0], fn.knotDomain[0], places=6)
    if count > 1:
        step = fn.length(1e-6) / (count - 1)
        for index, param in enumerate(call.result):
            case.assertAlmostEqual(fn.findLengthFromParam(param), step * index, delta=1e-3)


def _expect_matrices(case, call):
    """count 個のマトリクスで、位置がカーブ上(ローカル)にあり、正規直交。"""
    case.assertEqual(len(call.result), call.kwargs["count"])
    fn = _fn(call.target)
    params = call.target.getParamsAlong(call.kwargs["count"])
    for matrix, param in zip(call.result, params):
        case.assertIsInstance(matrix, Matrix)
        case.assertAlmostEqual(abs(om2.MMatrix(matrix).det3x3()), 1.0, places=5)
        if not _world(call.kwargs):
            case.assertSequenceAlmostEqual([matrix[12], matrix[13], matrix[14]], list(fn.getPointAtParam(param))[:3], places=5)


# ----------------------------------------------------------------------
# 同時に指定できない組


def _length_conflict(kwargs):
    """param を渡したときは tolerance を指定できない。"""
    return kwargs.get("param") is not None and "tolerance" in kwargs


def _param_conflict(kwargs):
    """point と length はどちらか1つ。length と tolerance、point と distanceUnit は同時に指定できない。"""
    point, length = kwargs.get("point"), kwargs.get("length")
    if (point is None) == (length is None):
        return True
    return (length is not None and "tolerance" in kwargs) or (point is not None and "distanceUnit" in kwargs)


def _second_order(kwargs):
    """secondOrder=True は what="derivatives" のときだけ。"""
    return kwargs.get("secondOrder") is True and kwargs.get("what", "point") != "derivatives"


#: 段2の数の引数の値(有限でない・型の違う値)。
NUMBER_INVALID = ("a", float("nan"), float("inf"), None, (1.0,))

#: NurbsCurve の正しい呼び方の表。
METHODS = (
    Method(
        "getCVs",
        _make_curve,
        values={"indices": (None, 0, 6, [0, 2], (), [3, 3, 1], range(2))},
        replace=("indices",),
        invalid={"indices": (-1, 7, True, "a", 1.5, [1.5], [0, -1], [99])},
        expect=_expect_cvs,
        plural=_make_curves,
    ),
    Method("mfn", _make_curve, expect=_expect_mfn, writes=False),
    Method("getNumCVs", _make_curve, expect=_expect_num_cvs, plural=_make_curves),
    Method("getKnots", _make_curve, expect=_expect_knots, plural=_make_curves),
    Method(
        "setKnots",
        _make_curve,
        args=(KNOTS,),
        values={"knots": (KNOTS, list(KNOTS), (0.0, 0.0, 0.0, 0.5, 2.0, 2.0, 3.0, 3.0, 3.0), (0, 0, 0, 1, 1, 2, 4, 4, 4))},
        replace=("knots",),
        invalid={
            "knots": (
                KNOTS[:-1],
                (*KNOTS, 3.0),
                tuple(reversed(KNOTS)),
                (0.0, 0.0, 0.0, 1.0, float("nan"), 2.0, 3.0, 3.0, 3.0),
                (0.0,) * 9,
                "abc",
                None,
                1.0,
                ("a",) * 9,
            )
        },
        expect=_expect_set_knots,
        state=_shape_state,
        roundTrip=RoundTrip("getKnots", value="knots"),
        limit=20,
    ),
    Method(
        "reduceKnotMultiplicity",
        _make_curve,
        args=(2.0,),
        values={"parameter": (2.0, 2, 1.0, 0.0, 3.0)},
        invalid={"parameter": NUMBER_INVALID},
        expect=_expect_reduce,
        state=_shape_state,
    ),
    Method(
        "removeKnot",
        _make_curve,
        args=(1.0,),
        values={"parameter": (1.0, 2.0, 2, 0.5, 0.0, 3.0)},
        invalid={"parameter": NUMBER_INVALID},
        expect=_expect_remove,
        state=_shape_state,
    ),
    Method("makeMultipleEndKnots", _make_uniform, expect=_expect_end_knots, state=_shape_state),
    Method(
        "getLength",
        _make_curve,
        values={"param": (None, 0.0, 1.5, 3.0, 2), "tolerance": (1e-6, 1e-3, 0.0, -1.0), "distanceUnit": tuple(UNIT_FACTORS)},
        replace=("param", "tolerance", "distanceUnit"),
        invalid={"param": NUMBER_INVALID[:-2], "tolerance": ("a", float("nan"), float("inf"), 0.0), "distanceUnit": ("parsec", 1.5, "")},
        conflicts=(SPACE, _length_conflict),
        expect=_expect_length,
        plural=_make_curves,
    ),
    Method("getArea", _make_circle, conflicts=(SPACE,), expect=_expect_area),
    Method(
        "rebuild",
        _make_curve,
        values={"spans": (None, 1, 4, 0, -1), "degree": (None, 1, 2, 3, 5, 7, 4, 0)},
        replace=("spans", "degree"),
        invalid={"spans": (True, 1.5, "a", 0, -1), "degree": (True, 1.5, "a", 4, 6, 0)},
        expect=_expect_rebuild,
        state=_shape_state,
        limit=30,
    ),
    Method("reverseDirection", _make_curve, expect=_expect_reverse, state=_shape_state),
    Method(
        "getCollocatedCVGroups",
        _make_circle,
        values={"tolerance": (1e-6, 1e-3, 1.0, 1000.0, 0.0, -1.0)},
        replace=("tolerance",),
        invalid={"tolerance": ("a", float("nan"), None, 0.0, -1e-6)},
        conflicts=(SPACE,),
        expect=_expect_collocated,
    ),
    Method("getParamRange", _make_curve, expect=_expect_range, plural=_make_curves),
    Method(
        "getParam",
        _make_curve,
        kwargs={"length": 1.0},
        values={
            "point": (None, *POINT_VALUES),
            "length": (None, 0.0, 1.0, 5.0, 2, -1.0, 1000.0),
            "tolerance": (1e-7, 0.0, 1e-3, 2.0),
            "distanceUnit": ("cm", "mm", "m", "in", None),
        },
        replace=("point", "length", "tolerance", "distanceUnit"),
        invalid={
            "point": tuple(value for value in POINT_INVALID if value is not None),
            "length": ("a", float("nan"), float("inf"), -1.0, 1e9),
            "tolerance": ("a", float("nan"), float("inf"), -1.0),
            "distanceUnit": ("parsec", 1.5),
        },
        conflicts=(SPACE, _param_conflict),
        expect=_expect_param,
        limit=120,
    ),
    Method(
        "isPointOnCurve",
        _make_curve,
        args=(_curve_point(1.5),),
        values={"point": POINT_VALUES, "tolerance": (1e-7, 0.0, 0.5, 2.0)},
        replace=("point", "tolerance"),
        invalid={"point": POINT_INVALID, "tolerance": ("a", float("nan"), float("inf"), -1.0, None)},
        conflicts=(SPACE,),
        expect=_expect_on_curve,
    ),
    Method(
        "getClosestPoint",
        _make_curve,
        args=(_curve_point(1.5),),
        values={"point": (*POINT_VALUES, (100.0, 100.0, 100.0))},
        replace=("point",),
        invalid={"point": POINT_INVALID},
        conflicts=(SPACE,),
        expect=_expect_closest,
        plural=_make_curves,
    ),
    Method(
        "getAtParam",
        _make_curve,
        args=(1.5,),
        values={"param": (0.0, 0.5, 1.5, 2.5, 3.0, 2, -1.0, 1000.0)},
        replace=("param",),
        invalid={"param": NUMBER_INVALID, "what": ("position", 1.5, None)},
        conflicts=(SPACE, _second_order),
        expect=_expect_at_param,
        limit=120,
    ),
    Method(
        "getParamsAlong",
        _make_curve,
        args=(5,),
        values={"count": (1, 2, 5, 13, 0, -1)},
        replace=("count",),
        invalid={"count": (True, 1.5, "a", None, 0, -3)},
        conflicts=(SPACE,),
        expect=_expect_params_along,
        plural=_make_curves,
    ),
    Method(
        "getMatricesAlong",
        _make_curve,
        args=(4,),
        values={
            "count": (1, 4, 9),
            "up": (None, (0.0, 0.0, 1.0), [0, 0, 2], om2.MVector(0.0, 0.0, -1.0), Vector(0.0, 1.0, 1.0)),
            "aimAxis": AXES,
            "upAxis": AXES,
        },
        replace=("count", "up", "aimAxis", "upAxis"),
        invalid={
            "count": (True, 1.5, 0, -1),
            "up": ((0.0, 0.0), (0.0, 0.0, 0.0), (float("nan"), 0.0, 1.0), "abc", object()),
            "aimAxis": ("w", "", 1.5, None),
            "upAxis": ("w", "x", 1.5, None),
        },
        conflicts=(SPACE,),
        expect=_expect_matrices,
        limit=120,
    ),
)


class NurbsCurveArgumentSweepTest(ArgumentSweepCase):
    """NurbsCurveのメソッドの引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
