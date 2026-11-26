"""PointComponent・PointComponents の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
メッシュの頂点(Vertex・Vertices)で全部のメソッドを、カーブの CV・サーフェスの CV・ラティスの点では
getPosition・setPosition を確かめる。
"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Method, RoundTrip

from mlib.components import CV, LatticePoint, SurfaceCV, Vertex, Vertices
from mlib.maths import Vector

#: 長い名前と短縮名の組(同時に指定できない)。
SPACE = ("worldSpace", "ws")
#: polyCube(1辺2cm)の頂点のオブジェクト空間の座標。
CUBE_POINTS = ((-1, -1, 1), (1, -1, 1), (-1, 1, 1), (1, 1, 1), (-1, 1, -1), (1, 1, -1), (-1, -1, -1), (1, -1, -1))
#: 1点の位置の候補(タプル・リスト・om2 の型・mlib の型・大きい値・成分1つ)。
POINT_VALUES = ((1.0, 2.0, 3.0), [0, 0, 0], om2.MPoint(1.0, -2.0, 0.5), om2.MVector(4.0, 5.0, 6.0), Vector(-3.0, 0.0, 7.5), (1000.0, -2.0, 0.25), 2.5)
#: 1点の位置の段2の誤った値(成分の数・型・有限でない値)。
POINT_INVALID = ((1.0, 2.0), (1.0, 2.0, 3.0, 4.0), "abc", None, (float("nan"), 0.0, 0.0), object())
#: mirror の軸の候補(軸・面・面の文字の順・番号)。
MIRROR_AXES = ("x", "y", "z", "YZ", "XZ", "XY", "zy", 0, 1, 2)


def _transformed(transform):
    """transform を移動・回転・拡大する。"""
    cmds.setAttr(transform + ".translate", 1.0, 2.0, 3.0)
    cmds.setAttr(transform + ".rotate", 0.0, 30.0, 0.0)
    cmds.setAttr(transform + ".scale", 2.0, 1.0, 0.5)


def _mesh(case):
    """移動・回転・拡大した、1辺2cm の履歴なし polyCube の Mesh を返す。"""
    transform = cmds.polyCube(name=case.name("cube#"), width=2, height=2, depth=2, constructionHistory=False)[0]
    _transformed(transform)
    return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])


def _vertex(case):
    """頂点2を返す。"""
    return Vertex(_mesh(case), 2)


def _vertex_pair(case):
    """複数形の確かめ用に、(Vertices[2, 5], 単数の並び) を返す。"""
    mesh = _mesh(case)
    return Vertices(mesh, [2, 5]), [Vertex(mesh, 2), Vertex(mesh, 5)]


def _vertices(case):
    """頂点 [0, 2, 5] の Vertices を返す。"""
    return Vertices(_mesh(case), [0, 2, 5])


def _curve_cv(case):
    """移動した3次の履歴なしカーブの CV 2 を返す。"""
    transform = cmds.curve(name=case.name("crv#"), degree=3, point=[(0, 0, 0), (1, 1, 0), (2, 0, 1), (3, 1, 1), (4, 0, 0)])
    _transformed(transform)
    return CV(mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0]), 2)


def _surface_cv(case):
    """移動した履歴なし nurbsPlane の CV (1, 2) を返す。"""
    transform = cmds.nurbsPlane(name=case.name("plane#"), width=4, patchesU=2, patchesV=2, degree=3, axis=(0, 1, 0), constructionHistory=False)[0]
    _transformed(transform)
    return SurfaceCV(mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0]), (1, 2))


def _lattice_point(case):
    """メッシュに付けたラティス(2×3×2)の点 (1, 1, 0) を返す。"""
    cube = cmds.polyCube(name=case.name("latticeCube#"), constructionHistory=False)[0]
    _, lattice, _ = cmds.lattice(cube, name=case.name("ffd#"), divisions=(2, 3, 2), objectCentered=True)
    _transformed(lattice)
    return LatticePoint(mlib.getNode(cmds.listRelatives(lattice, shapes=True, fullPath=True)[0]), (1, 1, 0))


def _all_points(shape):
    """Shape のすべての点の、オブジェクト空間の座標を cmds で読む。"""
    name = shape.getName(full=True)
    pattern = {"mesh": ".vtx[*]", "nurbsCurve": ".cv[*]", "nurbsSurface": ".cv[*][*]", "lattice": ".pt[*][*][*]"}[cmds.nodeType(name)]
    values = cmds.xform(name + pattern, query=True, translation=True, objectSpace=True)
    return [round(value, 5) for value in values]


def _point_state(case, target):
    """Shape のすべての点の座標と、シーンの状態。"""
    return [_all_points(target.shape), case.sceneState()]


def _world(kwargs):
    """worldSpace・ws のどちらかで True を指定したか。"""
    return kwargs.get("worldSpace", kwargs.get("ws", False)) is True


def _position(component, world):
    """1つの点の座標を cmds で読む。"""
    return cmds.xform(component.getName(full=True), query=True, translation=True, worldSpace=world, objectSpace=not world)


def _expect_position(case, call):
    """cmds.xform の座標と同じ(複数の点なら持っている順)。"""
    world = _world(call.kwargs)
    if hasattr(call.target, "indices"):
        expected = [_position(item, world) for item in call.target]
        case.assertEqual(len(call.result), len(expected))
        for actual, point in zip(call.result, expected):
            case.assertSequenceAlmostEqual(actual, point, places=4)
    else:
        case.assertSequenceAlmostEqual(call.result, _position(call.target, world), places=4)


def _xyz(value):
    """3成分の値なら座標の並び、そうでなければ None を返す。"""
    if isinstance(value, (int, float)) or value is None:
        return None
    items = list(value)
    return [float(item) for item in items[:3]] if len(items) >= 3 else None


def _expect_set_position(case, call):
    """絶対座標で3成分を書いたら、cmds.xform の座標がその値になる。"""
    kwargs = call.kwargs
    point = _xyz(kwargs["value"])
    if kwargs.get("relative") or kwargs.get("axis") is not None or point is None:
        return
    targets = list(call.target) if hasattr(call.target, "indices") else [call.target]
    points = [_xyz(item) for item in kwargs["value"]] if kwargs.get("each") else [point] * len(targets)
    for component, expected in zip(targets, points):
        case.assertSequenceAlmostEqual(_position(component, _world(kwargs)), expected, places=4)


def _skip_trip(kwargs):
    """相対・1成分・3成分でない値は、書いた値を読み直して比べない。"""
    return kwargs.get("relative") or kwargs.get("axis") is not None or kwargs.get("each") or _xyz(kwargs.get("value")) is None


def _expect_mirror(case, call):
    """オブジェクト空間では、反転した軸の成分が 2 * pivot - 元の値 になる。"""
    kwargs = call.kwargs
    if _world(kwargs):
        return
    axis = kwargs.get("axis", "x")
    column = axis if isinstance(axis, int) else {"x": 0, "y": 1, "z": 2, "yz": 0, "zy": 0, "xz": 1, "zx": 1, "xy": 2, "yx": 2}[axis.lower()]
    pivot = list(kwargs.get("pivot", (0.0, 0.0, 0.0)))
    for component in call.target:
        expected = list(CUBE_POINTS[component.index])
        expected[column] = 2.0 * pivot[column] - expected[column]
        case.assertSequenceAlmostEqual(_position(component, False), expected, places=4)


def _expect_center(case, call):
    """持っている点の座標の平均。"""
    points = [_position(item, _world(call.kwargs)) for item in call.target]
    case.assertSequenceAlmostEqual(call.result, [sum(point[axis] for point in points) / len(points) for axis in range(3)], places=4)


def _set_position(setup, plural=None, limit=120):
    """PointComponent.setPosition の表の行を作る。"""
    return Method(
        "setPosition",
        setup,
        args=((1.0, 2.0, 3.0),),
        values={"value": POINT_VALUES, "axis": ("X",)},
        invalid={"value": POINT_INVALID, "axis": (1.5, "w", "xy")},
        conflicts=(SPACE,),
        state=_point_state,
        expect=_expect_set_position,
        roundTrip=RoundTrip("getPosition", shared=SPACE, skip=_skip_trip, places=4),
        plural=plural,
        limit=limit,
    )


class PointComponentArgumentSweepTest(ArgumentSweepCase):
    """PointComponent の公開メソッドの引数を網羅する(メッシュの頂点で確かめる)。"""

    METHODS = (Method("getPosition", _vertex, conflicts=(SPACE,), expect=_expect_position, plural=_vertex_pair), _set_position(_vertex, plural=_vertex_pair))


class PointComponentsArgumentSweepTest(ArgumentSweepCase):
    """PointComponents の公開メソッドの引数を網羅する(メッシュの頂点で確かめる)。"""

    METHODS = (
        Method("getPosition", _vertices, conflicts=(SPACE,), expect=_expect_position),
        Method(
            "setPosition",
            _vertices,
            args=((1.0, 2.0, 3.0),),
            values={"value": (*POINT_VALUES, [(0.0, 0.0, 0.0), (1.0, 1.0, 1.0), (2.0, 2.0, 2.0)], [1.0, 2.0, 3.0], [om2.MPoint(1, 2, 3)] * 3), "axis": ("X",)},
            invalid={"value": (*POINT_INVALID, [(0.0, 0.0, 0.0)] * 2), "axis": (1.5, "w")},
            conflicts=(SPACE,),
            state=_point_state,
            expect=_expect_set_position,
            limit=200,
        ),
        Method(
            "mirror",
            _vertices,
            values={"axis": MIRROR_AXES, "pivot": ((0.0, 0.0, 0.0), (1.0, 2.0, 3.0), [0.5, 0.0, 0.0], om2.MPoint(1.0, 0.0, 0.0))},
            replace=("axis",),
            invalid={"axis": (3, -1, "w", "xyz", 1.5, None), "pivot": ((1.0, 2.0), "abc", None, (float("nan"), 0.0, 0.0), object())},
            conflicts=(SPACE,),
            state=_point_state,
            expect=_expect_mirror,
            limit=60,
        ),
        Method("getCenter", _vertices, conflicts=(SPACE,), expect=_expect_center),
    )


class CVArgumentSweepTest(ArgumentSweepCase):
    """カーブの CV の getPosition・setPosition の引数を網羅する。"""

    METHODS = (Method("getPosition", _curve_cv, conflicts=(SPACE,), expect=_expect_position), _set_position(_curve_cv, limit=40))


class SurfaceCVArgumentSweepTest(ArgumentSweepCase):
    """サーフェスの CV の getPosition・setPosition の引数を網羅する。"""

    METHODS = (Method("getPosition", _surface_cv, conflicts=(SPACE,), expect=_expect_position), _set_position(_surface_cv, limit=40))


class LatticePointArgumentSweepTest(ArgumentSweepCase):
    """ラティスの点の getPosition・setPosition の引数を網羅する。"""

    METHODS = (Method("getPosition", _lattice_point, conflicts=(SPACE,), expect=_expect_position), _set_position(_lattice_point, limit=40))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
