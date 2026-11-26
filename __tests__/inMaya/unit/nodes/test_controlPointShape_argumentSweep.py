"""点を持つシェイプ(Mesh・NurbsCurve・NurbsSurface)の getPoints・setPoints・mirror の引数を、表から網羅して確かめる(段1〜3)。

3つのメソッドは ``_ControlPointShape`` にあり、形状ごとに点の種類と書き込みの手順が違うので、形状ごとに1つの表にする。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Lazy, Method, RoundTrip

from mlib.maths import Vector

#: ワールド空間の長い名前と短縮名(同時に指定できない)。
SPACE = ("worldSpace", "ws")
#: 開いた次数3のカーブのCV。
CURVE_POINTS = ((0.0, 0.0, 0.0), (1.0, 2.0, 0.5), (2.0, 0.0, -1.0), (3.0, -2.0, 0.0), (4.0, 0.5, 1.0))
#: 書き込む型の名前と、点の並びへの変換。
KINDS = {
    "tuple": lambda points: [tuple(point) for point in points],
    "list": lambda points: [list(point) for point in points],
    "Vector": lambda points: [Vector(*point) for point in points],
    "MPointArray": lambda points: om2.MPointArray([om2.MPoint(*point) for point in points]),
    "MVector": lambda points: [om2.MVector(*point) for point in points],
}
#: 反転の軸の名前・番号と、反転する成分の番号。
AXIS_INDEX = {"x": 0, "y": 1, "z": 2, "yz": 0, "xz": 1, "xy": 2, "zy": 0, "zx": 1, "yx": 2}


def _place(case, transform):
    """トランスフォームを動かし、回転・拡大する(ワールド空間とローカル空間の値を違える)。シェイプを名前空間に移す。"""
    cmds.setAttr(transform + ".translate", 1.0, 2.0, 3.0)
    cmds.setAttr(transform + ".rotate", 10.0, 20.0, 30.0)
    cmds.setAttr(transform + ".scale", 2.0, 1.0, 0.5)
    # 作成コマンドはシェイプを名前空間の外に作るので、名前空間の中へ移す。
    for shape in cmds.listRelatives(transform, shapes=True, fullPath=True) or []:
        cmds.rename(shape, case.name("shape#"))
    shape = mlib.getNode(transform).getShape()
    # mirror の確かめ用に、書く前の点を両方の空間で残す(書き込むメソッドは呼ぶたびに作り直す)。
    case.before = {world: _raw(shape.getName(full=True), world) for world in (False, True)}
    return shape


def _make_mesh(case):
    return _place(case, cmds.polyCube(name=case.name("cube#"), width=2.0, height=3.0, depth=1.0, constructionHistory=False)[0])


def _make_curve(case):
    return _place(case, cmds.curve(name=case.name("curve#"), degree=3, point=CURVE_POINTS))


def _make_surface(case):
    return _place(case, cmds.nurbsPlane(name=case.name("surface#"), axis=(0, 1, 0), width=4, patchesU=2, patchesV=3, constructionHistory=False)[0])


def _plural(make):
    def plural(case):
        singles = [make(case), make(case)]
        return mlib.Nodes(singles), singles

    return plural


def _path(name):
    selection = om2.MSelectionList()
    selection.add(name)
    return selection.getDagPath(0)


def _raw(name, world):
    """om2 で読んだ点(ウェイトで割らないXYZ)の並び。"""
    path = _path(name)
    space = om2.MSpace.kWorld if world else om2.MSpace.kObject
    if path.hasFn(om2.MFn.kMesh):
        points = om2.MFnMesh(path).getPoints(space)
    elif path.hasFn(om2.MFn.kNurbsCurve):
        points = om2.MFnNurbsCurve(path).cvPositions(space)
    else:
        points = om2.MFnNurbsSurface(path).cvPositions(space)
    return [(point.x, point.y, point.z) for point in points]


def _shape_state(case, target):
    """sceneState に、名前空間の形状の点(ローカル)を足す。"""
    state = case.sceneState()
    for name in cmds.ls(case.ns + ":*", type=("mesh", "nurbsCurve", "nurbsSurface"), long=True) or []:
        state.append((name, _raw(name, False)))
    return state


def _world(kwargs):
    return bool(kwargs.get("worldSpace", kwargs.get("ws", False)))


def _moved(kind, world=False, count=0):
    """今の点を少し動かした並び(count で数を変える)を、呼ぶ直前に作る値。"""

    def make(case):
        name = cmds.ls(case.ns + ":*", type=("mesh", "nurbsCurve", "nurbsSurface"), long=True)[0]
        points = [(x + 0.5 * index, y - 0.25, z + 1.0) for index, (x, y, z) in enumerate(_raw(name, world))]
        if count:
            points = points[:count] if count < 0 else points + points[:count]
        return KINDS[kind](points)

    label = f"<動かした点({kind}{', ワールド' if world else ''}{f', 数{count:+d}' if count else ''})>"
    return Lazy(make, label)


def _broken(value):
    """点の数は同じで、1つの点だけを value にした並び。"""

    def make(case):
        name = cmds.ls(case.ns + ":*", type=("mesh", "nurbsCurve", "nurbsSurface"), long=True)[0]
        points = [tuple(point) for point in _raw(name, False)]
        points[1] = value
        return points

    return Lazy(make, f"<1点が{value!r}の並び>")


# ----------------------------------------------------------------------
# expect


def _xform_points(name, world):
    """cmds.xform で読んだ点(メッシュは頂点、カーブはCV)。サーフェスは None。"""
    if cmds.objectType(name) == "nurbsSurface":
        return None
    component = ".vtx[*]" if cmds.objectType(name) == "mesh" else ".cv[*]"
    flat = cmds.xform(name + component, query=True, translation=True, worldSpace=world, objectSpace=not world)
    return [tuple(flat[i : i + 3]) for i in range(0, len(flat), 3)]


def _expect_get_points(case, call):
    """getPoints を om2 と、メッシュ・カーブは cmds.xform とも比べる。"""
    name = call.target.getName(full=True)
    world = _world(call.kwargs)
    case.assertTrue(all(isinstance(point, Vector) for point in call.result))
    flat = [value for point in call.result for value in point]
    case.assertSequenceAlmostEqual(flat, [value for point in _raw(name, world) for value in point], places=6)
    expected = _xform_points(name, world)
    if expected is not None:
        case.assertSequenceAlmostEqual(flat, [value for point in expected for value in point], places=4)


def _expect_set_points(case, call):
    """書いた点を、同じ空間で om2 から読み直して比べる。"""
    case.assertIsNone(call.result)
    points = [tuple(point)[:3] for point in call.kwargs["points"]]
    actual = _raw(call.target.getName(full=True), _world(call.kwargs))
    case.assertSequenceAlmostEqual([v for p in actual for v in p], [float(v) for p in points for v in p], places=4)


def _flat_index(name, item):
    if isinstance(item, int):
        return item
    return item[0] * om2.MFnNurbsSurface(_path(name)).numCVsInV + item[1]


def _expect_mirror(case, call):
    """選んだ点の軸の成分だけが 2 * pivot - 元の値 になり、ほかは変わらない(選んだ空間で比べる)。"""
    case.assertIsNone(call.result)
    kwargs = call.kwargs
    name = call.target.getName(full=True)
    world = _world(kwargs)
    axis = kwargs.get("axis", "x")
    axis = axis if isinstance(axis, int) else AXIS_INDEX[axis.lower()]
    pivot = list(kwargs.get("pivot", (0.0, 0.0, 0.0)))
    before = case.before[world]
    indices = kwargs.get("indices")
    chosen = set(range(len(before))) if indices is None else {_flat_index(name, item) for item in indices}
    expected = []
    for index, point in enumerate(before):
        point = list(point)
        if index in chosen:
            point[axis] = 2.0 * pivot[axis] - point[axis]
        expected.append(point)
    actual = _raw(name, world)
    case.assertSequenceAlmostEqual([v for p in actual for v in p], [v for p in expected for v in p], places=4)


# ----------------------------------------------------------------------
# 表


def _methods(make, indices, bad_indices):
    """1つの形状の3つのメソッドの表を作る。

    Args:
        make (callable): 形状を作る関数。
        indices (tuple): mirror の indices の候補(形状ごとに足すもの)。
        bad_indices (tuple): mirror の indices の誤った値(形状ごとに足すもの)。
    """
    return (
        Method("getPoints", make, conflicts=(SPACE,), expect=_expect_get_points, plural=_plural(make)),
        Method(
            "setPoints",
            make,
            args=(_moved("tuple"),),
            values={"points": (*(_moved(kind) for kind in KINDS), _moved("tuple", world=True))},
            replace=("points",),
            invalid={
                "points": (
                    _moved("tuple", count=-1),
                    _moved("tuple", count=1),
                    _broken((float("nan"), 0.0, 0.0)),
                    _broken((1.0, 2.0)),
                    _broken(("a", 0.0, 0.0)),
                    _broken(None),
                    "abc",
                    None,
                    1.0,
                    object(),
                )
            },
            conflicts=(SPACE,),
            expect=_expect_set_points,
            state=_shape_state,
            roundTrip=RoundTrip("getPoints", value="points", shared=SPACE, places=4),
            limit=25,
        ),
        Method(
            "mirror",
            make,
            values={
                "axis": ("zy", "Xz", "yX", 2, 3, "w"),
                "pivot": ((0.0, 0.0, 0.0), (1.0, 2.0, 3.0), [0.5, 0, 0], om2.MVector(1.0, -1.0, 0.5), Vector(-2.0, 0.0, 1.0)),
                "indices": (None, [0, 1], [], [2, 2], range(3), *indices),
            },
            replace=("pivot", "indices"),
            invalid={
                "axis": (1.5, "w", "", "xyz", None, -1, 3),
                "pivot": ((1.0, 2.0), "abc", (float("nan"), 0.0, 0.0), None, object()),
                "indices": ([-1], [1000], ["a"], [1.5], 1.5, *bad_indices),
            },
            conflicts=(SPACE,),
            expect=_expect_mirror,
            state=_shape_state,
            limit=25,
        ),
    )


class MeshControlPointArgumentSweepTest(ArgumentSweepCase):
    """Mesh の getPoints・setPoints・mirror の引数を網羅する。"""

    METHODS = _methods(_make_mesh, (), ())


class NurbsCurveControlPointArgumentSweepTest(ArgumentSweepCase):
    """NurbsCurve の getPoints・setPoints・mirror の引数を網羅する。"""

    METHODS = _methods(_make_curve, (), ())


class NurbsSurfaceControlPointArgumentSweepTest(ArgumentSweepCase):
    """NurbsSurface の getPoints・setPoints・mirror の引数を網羅する(番号は通し番号と (u, v))。"""

    METHODS = _methods(_make_surface, ([(1, 1), 0], [(4, 5)]), ([(5, 0)], [(0, 6)], [(0,)]))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
