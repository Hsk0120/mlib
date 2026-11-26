"""NurbsSurfaceのメソッドの引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
点の読み書きと反転(getPoints・setPoints・mirror)は ``test_controlPointShape_argumentSweep.py`` で確かめる。
"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Lazy, Method

from mlib.maths import Matrix, Vector

#: ワールド空間の長い名前と短縮名(同時に指定できない)。
SPACE = ("worldSpace", "ws")
#: 軸の名前。
AXES = ("x", "y", "z", "-x", "-y", "-z")
#: 1パッチの平面の明示UV(4つの角)。
UVS = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
#: 点(tuple・list・MPoint・MVector)。曲面は y=0 の平面(ローカル)で、幅10。
POINT_VALUES = ((1.0, 0.0, 2.0), [0, 0, 0], om2.MPoint(-3.0, 0.0, 4.0), om2.MVector(2.0, 0.0, -2.0), (1.0, 3.0, 2.0), (100.0, 0.0, 0.0))
#: 点の誤った値(成分の数・型・有限でない成分)。
POINT_INVALID = ((1.0, 2.0), (1.0, 2.0, 3.0, 4.0), "abc", None, object(), (float("nan"), 0.0, 0.0), (1.0, "a", 0.0))
#: 許容誤差の候補と誤った値。
TOLERANCE_VALUES = (1e-7, 0.0, 0.5, 5.0)
#: 許容誤差の誤った値。
TOLERANCE_INVALID = ("a", float("nan"), float("inf"), -1.0, None)
#: パラメーターの誤った値。
PARAM_INVALID = ("a", float("nan"), float("inf"), None, -0.5, 1.5)


def _surface(case, patches=4, uvs=False, trim=False):
    """y軸向きで幅10の平面(次数3)を作り、動かして2倍にしたシェイプを返す。

    Args:
        case (ArgumentSweepCase): テストケース。
        patches (int): U・Vのパッチの数。4ならノットは0・0.25・0.5・0.75・1。
        uvs (bool): Trueなら明示UVを入れる(1パッチの平面だけ)。
        trim (bool): Trueなら中央に穴を開けるトリムをする。
    """
    name = cmds.nurbsPlane(name=case.name("surface#"), axis=(0, 1, 0), width=10, patchesU=patches, patchesV=patches, constructionHistory=False)[0]
    # cmds.nurbsPlane はシェイプを名前空間の外に作るので、名前空間の中へ移す。
    for shape in cmds.listRelatives(name, shapes=True, fullPath=True) or []:
        cmds.rename(shape, case.name("surfaceShape#"))
    if trim:
        boundary = cmds.curveOnSurface(name, degree=1, positionUV=[(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8), (0.2, 0.2)])
        cmds.trim(name, boundary, constructionHistory=False, replaceOriginal=True, locatorU=0.05, locatorV=0.05, selected=0)
    cmds.setAttr(name + ".translate", 1.0, 2.0, 3.0)
    cmds.setAttr(name + ".scale", 2.0, 2.0, 2.0)
    shape = mlib.getNode(name).getShape()
    if uvs:
        shape.setUVData(UVS, [4], [0, 1, 2, 3], fast=True)
    return shape


def _make_surface(case):
    return _surface(case)


def _make_single(case):
    return _surface(case, patches=1)


def _make_uv_surface(case):
    return _surface(case, patches=1, uvs=True)


def _make_trimmed(case):
    return _surface(case, patches=1, trim=True)


def _make_surfaces(case):
    singles = [_surface(case), _surface(case)]
    return mlib.Nodes(singles), singles


def _fn(target):
    selection = om2.MSelectionList()
    selection.add(target if isinstance(target, str) else target.getName(full=True))
    return om2.MFnNurbsSurface(selection.getDagPath(0))


def _uv_data(fn):
    try:
        us, vs = fn.getUVs()
        counts, indices = fn.getAssignedUVs()
    except RuntimeError:
        return None
    return list(zip(us, vs)), list(counts), list(indices)


def _shape_state(case, target):
    """sceneState に、名前空間の曲面のCV・ノット・明示UVを足す。"""
    state = case.sceneState()
    for name in cmds.ls(case.ns + ":*", type="nurbsSurface", long=True) or []:
        fn = _fn(name)
        state.append((name, [tuple(point) for point in fn.cvPositions()], list(fn.knotsInU()), list(fn.knotsInV()), _uv_data(fn)))
    return state


def _world(kwargs):
    return bool(kwargs.get("worldSpace", kwargs.get("ws", False)))


def _space(kwargs):
    return om2.MSpace.kWorld if _world(kwargs) else om2.MSpace.kObject


def _knots(direction, change=None):
    """今のノット列(change で内側の値を変えたもの)を、呼ぶ直前に作る値。"""

    def make(case):
        fn = _fn(cmds.ls(case.ns + ":*", type="nurbsSurface", long=True)[0])
        values = list(fn.knotsInU() if direction == "u" else fn.knotsInV())
        return change(values) if change else values

    return Lazy(make, f"<{direction}のノット{'(変更)' if change else ''}>")


def _move_inner(values):
    values[4] = 0.4
    return values


# ----------------------------------------------------------------------
# expect


def _expect_mfn(case, call):
    case.assertIsInstance(call.result, om2.MFnNurbsSurface)


def _expect_num_cvs(case, call):
    shape = call.target.getName(full=True)
    case.assertEqual(call.result, (cmds.getAttr(shape + ".spansU") + 3, cmds.getAttr(shape + ".spansV") + 3))


def _expect_form(case, call):
    shape = call.target.getName(full=True)
    forms = {0: om2.MFnNurbsSurface.kOpen, 1: om2.MFnNurbsSurface.kClosed, 2: om2.MFnNurbsSurface.kPeriodic}
    case.assertEqual(call.result, (forms[cmds.getAttr(shape + ".formU")], forms[cmds.getAttr(shape + ".formV")]))


def _expect_range(case, call):
    shape = call.target.getName(full=True)
    case.assertSequenceAlmostEqual(call.result[0], cmds.getAttr(shape + ".minMaxRangeU")[0])
    case.assertSequenceAlmostEqual(call.result[1], cmds.getAttr(shape + ".minMaxRangeV")[0])


def _expect_knots(case, call):
    fn = _fn(call.target)
    case.assertEqual(call.result, (list(fn.knotsInU()), list(fn.knotsInV())))
    case.assertEqual(call.result[0], [0.0, 0.0, 0.0, 0.25, 0.5, 0.75, 1.0, 1.0, 1.0])


def _expect_set_knots(case, call):
    case.assertIsNone(call.result)
    fn = _fn(call.target)
    case.assertSequenceAlmostEqual(list(fn.knotsInU()), list(call.kwargs["uKnots"]))
    case.assertSequenceAlmostEqual(list(fn.knotsInV()), list(call.kwargs["vKnots"]))


def _expect_remove_knot(case, call):
    """削除した方向で、その値のノットが1つ(all=True ならすべて)減る。"""
    case.assertIsNone(call.result)
    fn = _fn(call.target)
    knots = list(fn.knotsInU() if call.kwargs.get("direction", "u") == "u" else fn.knotsInV())
    case.assertEqual(len(knots), 8)
    case.assertNotIn(call.kwargs["parameter"], knots)


def _expect_patch_shaders(case, call):
    shaders, indices = call.result
    expected, expected_indices = _fn(call.target).getConnectedShaders(0)
    case.assertEqual([node.getName() for node in shaders], [om2.MFnDependencyNode(node).name() for node in expected])
    case.assertEqual(indices, list(expected_indices))


def _expect_uv_data(case, call):
    case.assertEqual(call.result, _uv_data(_fn(call.target)))
    case.assertEqual(call.result[0], list(UVS))


def _expect_set_uv_data(case, call):
    case.assertIsNone(call.result)
    uvs, counts, indices = _uv_data(_fn(call.target))
    case.assertSequenceAlmostEqual([value for uv in uvs for value in uv], [float(value) for uv in call.kwargs["uvs"] for value in uv])
    case.assertEqual(counts, list(call.kwargs["counts"]))
    case.assertEqual(indices, list(call.kwargs["indices"]))


def _expect_clear_uv(case, call):
    case.assertIsNone(call.result)
    case.assertIsNone(_uv_data(_fn(call.target)))


def _expect_trim_info(case, call):
    fn = _fn(call.target)
    expected = [[(fn.boundaryType(r, b), fn.numEdges(r, b)) for b in range(fn.numBoundaries(r))] for r in range(fn.numRegions)]
    case.assertEqual(call.result, expected)
    case.assertEqual(call.result, [[(om2.MFnNurbsSurface.kOuter, 4), (om2.MFnNurbsSurface.kInner, 4)]])


def _expect_trim_curve(case, call):
    kwargs = call.kwargs
    curves = _fn(call.target).edge(kwargs["region"], kwargs["boundary"], kwargs["edge"], kwargs.get("parametric", False))
    case.assertEqual(len(call.result), len(curves))
    for data, curve in zip(call.result, curves):
        fn = om2.MFnNurbsCurve(curve)
        case.assertEqual(data["degree"], fn.degree)
        case.assertEqual(data["knots"], list(fn.knots()))
        case.assertEqual(data["cvs"], [(p.x, p.y, p.z, p.w) for p in fn.cvPositions()])


def _expect_trimmed_region(case, call):
    """切り落とした領域(穴の中)なら True。om2 は残る領域で True を返す。"""
    fn = _fn(call.target)
    case.assertEqual(call.result, not fn.isPointInTrimmedRegion(call.kwargs["u"], call.kwargs["v"]))


def _expect_ray(case, call):
    kwargs = call.kwargs
    ray = om2.MVector(*list(kwargs["direction"])[:3])
    found = _fn(call.target).intersect(om2.MPoint(*list(kwargs["origin"])[:3]), ray.normal(), tolerance=kwargs.get("tolerance", 1e-6), space=_space(kwargs))
    if found is None:
        case.assertIsNone(call.result)
        return
    case.assertSequenceAlmostEqual(call.result[0], list(found[0])[:3], places=5)
    case.assertAlmostEqual(call.result[1], found[1], places=5)
    case.assertAlmostEqual(call.result[2], found[2], places=5)


def _surface_index(shape, item):
    return item if isinstance(item, int) else item[0] * _fn(shape).numCVsInV + item[1]


def _expect_cvs(case, call):
    """getCVs の結果を、番号から作った cmds の名前(cv[u][v])と比べる。"""
    shape = call.target.getName(full=True)
    count_v = _fn(shape).numCVsInV
    indices = call.kwargs.get("indices")
    if indices is None:
        indices = range(_fn(shape).numCVsInU * count_v)
    elif isinstance(indices, int):
        indices = [indices]
    names = [f"{shape}.cv[{index // count_v}][{index % count_v}]" for index in (_surface_index(shape, item) for item in indices)]
    expected = set(cmds.ls(names, long=True, flatten=True) or []) if names else set()
    actual = set(cmds.ls(call.result, long=True, flatten=True) or []) if names else set()
    case.assertEqual(actual, expected)


def _expect_on_surface(case, call):
    point = om2.MPoint(*list(call.kwargs["point"])[:3])
    case.assertEqual(call.result, _fn(call.target).isPointOnSurface(point, call.kwargs.get("tolerance", 1e-7), _space(call.kwargs)))


def _expect_closest(case, call):
    point = om2.MPoint(*list(call.kwargs["point"])[:3])
    found, u, v = _fn(call.target).closestPoint(point, tolerance=1e-7, space=_space(call.kwargs))
    case.assertSequenceAlmostEqual(call.result[0], list(found)[:3], places=5)
    case.assertAlmostEqual(call.result[1], u, places=5)
    case.assertAlmostEqual(call.result[2], v, places=5)


def _expect_at_param(case, call):
    """getAtParam を om2 と比べる(point・normal・derivatives。tangents・matrix は長さと正規直交)。"""
    kwargs = call.kwargs
    fn = _fn(call.target)
    u, v, space = kwargs["u"], kwargs["v"], _space(kwargs)
    what = kwargs.get("what", "point")
    result = call.result
    if what == "point":
        case.assertSequenceAlmostEqual(result, list(fn.getPointAtParam(u, v, space))[:3], places=5)
    elif what == "normal":
        case.assertSequenceAlmostEqual(result, list(fn.normal(u, v, space).normal()), places=5)
    elif what == "derivatives":
        expected = fn.getDerivativesAtParam(u, v, space=space, secondOrder=kwargs.get("secondOrder", False))
        case.assertEqual(len(result), len(expected))
        case.assertSequenceAlmostEqual(result[0], list(expected[0])[:3], places=5)
    elif what == "tangents":
        case.assertEqual(len(result), 2)
        for tangent in result:
            case.assertAlmostEqual(tangent.length(), 1.0, places=6)
    else:
        case.assertIsInstance(result, Matrix)
        case.assertAlmostEqual(abs(om2.MMatrix(result).det3x3()), 1.0, places=5)
        case.assertSequenceAlmostEqual([result[12], result[13], result[14]], list(fn.getPointAtParam(u, v, space))[:3], places=5)
    if what in ("point", "normal"):
        case.assertIsInstance(result, Vector)


def _expect_area(case, call):
    """幅10の平面の面積は100、ワールド空間ではその4倍。"""
    case.assertAlmostEqual(call.result, 400.0 if _world(call.kwargs) else 100.0, places=4)


# ----------------------------------------------------------------------
# 同時に指定できない組


def _at_param_conflict(kwargs):
    """secondOrder=True は what="derivatives"、aimAxis・upAxis は what="matrix" のときだけ。"""
    what = kwargs.get("what", "point")
    if kwargs.get("secondOrder") is True and what != "derivatives":
        return True
    return what != "matrix" and ("aimAxis" in kwargs or "upAxis" in kwargs)


#: NurbsSurface の正しい呼び方の表。
METHODS = (
    Method("mfn", _make_surface, expect=_expect_mfn, writes=False),
    Method("getNumCVs", _make_surface, expect=_expect_num_cvs, plural=_make_surfaces),
    Method("getForm", _make_surface, expect=_expect_form, plural=_make_surfaces),
    Method("getParamRange", _make_surface, expect=_expect_range, plural=_make_surfaces),
    Method("getKnots", _make_surface, expect=_expect_knots, plural=_make_surfaces),
    Method(
        "setKnots",
        _make_surface,
        args=(_knots("u"), _knots("v")),
        values={"uKnots": (_knots("u"), _knots("u", _move_inner), _knots("u", tuple)), "vKnots": (_knots("v"), _knots("v", _move_inner))},
        replace=("uKnots", "vKnots"),
        invalid={
            "uKnots": (
                _knots("u", lambda values: values[:-1]),
                _knots("u", lambda values: values[::-1]),
                _knots("u", lambda values: [0.0] * len(values)),
                "abc",
                None,
                1.0,
            ),
            "vKnots": (_knots("v", lambda values: [*values, 1.0]), _knots("v", lambda values: [float("nan")] * len(values)), ("a",) * 9, object()),
        },
        expect=_expect_set_knots,
        state=_shape_state,
        limit=20,
    ),
    Method(
        "removeKnot",
        _make_surface,
        args=(0.5,),
        values={"parameter": (0.5, 0.25, 0.75, 0.0, 1.0, 0.3), "direction": ("u", "v", "w")},
        replace=("parameter", "direction"),
        invalid={"parameter": ("a", float("nan"), float("inf"), None), "direction": ("w", "U", 1.5, None)},
        expect=_expect_remove_knot,
        state=_shape_state,
        limit=30,
    ),
    Method("getPatchShaders", _make_surface, expect=_expect_patch_shaders),
    Method("getUVData", _make_uv_surface, expect=_expect_uv_data),
    Method(
        "setUVData",
        _make_single,
        args=(UVS, [4], [0, 1, 2, 3]),
        kwargs={"fast": True},
        values={
            "uvs": (UVS, [list(uv) for uv in UVS], ((0.0, 0.0), (0.5, 0.0), (0.5, 0.5), (0.0, 0.5), (1, 1)), ((0.25, 0.75),)),
            "counts": ([4], (4,), [0]),
            "indices": ([0, 1, 2, 3], (3, 2, 1, 0), [0, 0, 0, 0], []),
        },
        replace=("uvs", "counts", "indices"),
        invalid={
            "uvs": ((), [(0.0, 0.0, 0.0)] * 4, [(float("nan"), 0.0)] * 4, "abc", None, [("a", 0.0)] * 4),
            "counts": ([4, 4], [5], [4.0], ["a"], None),
            "indices": ([0, 1, 2, 9], [0, 1, 2], [-1, 0, 1, 2], [0.0, 1.0, 2.0, 3.0], None),
            "fast": (1, "yes", False),
        },
        expect=_expect_set_uv_data,
        state=_shape_state,
        limit=30,
    ),
    Method("clearUVData", _make_uv_surface, expect=_expect_clear_uv, state=_shape_state),
    Method("getTrimBoundaryInfo", _make_trimmed, expect=_expect_trim_info),
    Method(
        "getTrimBoundaryCurveData",
        _make_trimmed,
        args=(0, 0, 0),
        values={"region": (0,), "boundary": (0, 1), "edge": (0, 1, 2, 3)},
        replace=("region", "boundary", "edge"),
        invalid={"region": (1, -1, 1.5, True, "a", None), "boundary": (2, -1, 1.5, None), "edge": (4, -1, 1.5, None)},
        expect=_expect_trim_curve,
    ),
    Method(
        "isPointInTrimmedRegion",
        _make_trimmed,
        args=(0.5, 0.5),
        values={"u": (0.5, 0.05, 0.0, 1.0, 1), "v": (0.5, 0.05, 0.95, 0)},
        replace=("u", "v"),
        invalid={"u": PARAM_INVALID, "v": PARAM_INVALID},
        expect=_expect_trimmed_region,
    ),
    Method(
        "getRayIntersection",
        _make_single,
        args=((0.0, 5.0, 0.0), (0.0, -1.0, 0.0)),
        values={
            "origin": ((0.0, 5.0, 0.0), [1, 5, 1], om2.MPoint(2.0, -5.0, 2.0), om2.MVector(10.0, 5.0, 10.0), (1.0, 2.0, 3.0)),
            "direction": ((0.0, -1.0, 0.0), [0, -3, 0], om2.MVector(0.0, 1.0, 0.0), (1.0, 0.0, 0.0)),
            "tolerance": (1e-6, 1e-3, 1.0),
        },
        replace=("origin", "direction", "tolerance"),
        invalid={
            "origin": POINT_INVALID,
            "direction": ((0.0, 0.0, 0.0), (0.0, -1.0), "abc", None, (float("inf"), 0.0, 0.0)),
            "tolerance": ("a", float("nan"), float("inf"), 0.0, -1.0, None),
        },
        conflicts=(SPACE,),
        expect=_expect_ray,
        limit=80,
    ),
    Method(
        "getCVs",
        _make_surface,
        values={"indices": (None, 0, 48, [0, (1, 1)], (), [(0, 0), (0, 0)], [(6, 6), 3])},
        replace=("indices",),
        invalid={"indices": (-1, 49, True, "a", 1.5, [(0,)], [(7, 0)], [(0, -1)], [1.5])},
        expect=_expect_cvs,
        plural=_make_surfaces,
    ),
    Method(
        "isPointOnSurface",
        _make_surface,
        args=((1.0, 0.0, 2.0),),
        values={"point": POINT_VALUES, "tolerance": TOLERANCE_VALUES},
        replace=("point", "tolerance"),
        invalid={"point": POINT_INVALID, "tolerance": TOLERANCE_INVALID},
        conflicts=(SPACE,),
        expect=_expect_on_surface,
        limit=80,
    ),
    Method(
        "getClosestPoint",
        _make_surface,
        args=((1.0, 0.0, 2.0),),
        values={"point": POINT_VALUES},
        replace=("point",),
        invalid={"point": POINT_INVALID},
        conflicts=(SPACE,),
        expect=_expect_closest,
        plural=_make_surfaces,
    ),
    Method(
        "getAtParam",
        _make_surface,
        args=(0.5, 0.5),
        kwargs={"what": "matrix"},
        values={"u": (0.0, 0.3, 1.0, 1), "v": (0.0, 0.7, 1.0), "aimAxis": AXES, "upAxis": AXES},
        replace=("u", "v", "aimAxis", "upAxis"),
        invalid={"u": PARAM_INVALID, "v": PARAM_INVALID, "what": ("position", 1.5, None), "aimAxis": ("w", 1.5, None), "upAxis": ("w", 1.5, None)},
        conflicts=(SPACE, _at_param_conflict),
        expect=_expect_at_param,
        limit=150,
    ),
    Method("getArea", _make_surface, conflicts=(SPACE,), expect=_expect_area, plural=_make_surfaces),
)


class NurbsSurfaceArgumentSweepTest(ArgumentSweepCase):
    """NurbsSurfaceのメソッドの引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
