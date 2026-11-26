"""VertexFace・VertexFaces の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

VertexFaces は自身のメソッドを持たないので、VertexFace のメソッドを複数形から呼んだ結果で確かめる。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Method

from mlib.components import VertexFace, VertexFaces
from mlib.maths import Vector

#: 長い名前と短縮名の組(同時に指定できない)。
SPACE = ("worldSpace", "ws")
#: 色の候補(RGB・RGBA・om2 の色・リスト・範囲の外)。
COLOR_VALUES = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.5), om2.MColor((0.2, 0.3, 0.4, 1.0)), [0.2, 0.3, 0.4], (2.0, -1.0, 0.5))
#: 色の段2の誤った値(成分の数・型・有限でない値)。
COLOR_INVALID = ((1.0, 2.0), (1.0, 2.0, 3.0, 4.0, 5.0), "abc", None, (float("nan"), 0.0, 0.0), object())
#: 法線の候補(タプル・斜め・mlib の型・om2 の型・リスト・書かない)。
NORMAL_VALUES = ((0.0, 1.0, 0.0), (1.0, 1.0, 0.0), Vector(0.0, 0.0, 2.0), om2.MVector(0.0, 1.0, 1.0), [0.0, 0.0, 1.0], None)
#: 法線の段2の誤った値(長さ0・成分の数・型)。有限でない値は check=False では確かめない決まりなので入れない。
NORMAL_INVALID = ((0.0, 0.0, 0.0), (1.0, 2.0), (1.0, 2.0, 3.0, 4.0), "abc", object())


def _fn(shape):
    """メッシュの名前から MFnMesh を返す。"""
    selection = om2.MSelectionList()
    selection.add(shape)
    return om2.MFnMesh(selection.getDagPath(0))


def _mesh(case):
    """移動・回転・拡大した、1辺2cm の履歴なし polyCube の Mesh を返す。

    カラーセット ``cs1``(頂点 i の色は (0.1i, 0.2, 0.3, 1))を今のセットにし、色の無いカラーセット ``cs2``、
    map1 を写した UV セット ``map2`` も持つ。
    """
    transform = cmds.polyCube(name=case.name("cube#"), width=2, height=2, depth=2, constructionHistory=False)[0]
    cmds.setAttr(transform + ".translate", 1.0, 2.0, 3.0)
    cmds.setAttr(transform + ".rotate", 0.0, 30.0, 0.0)
    cmds.setAttr(transform + ".scale", 2.0, 1.0, 0.5)
    shape = cmds.listRelatives(transform, shapes=True, fullPath=True)[0]
    fn = _fn(shape)
    fn.createColorSet("cs2", False)
    fn.createColorSet("cs1", False)
    fn.setCurrentColorSetName("cs1")
    fn.setVertexColors([om2.MColor((0.1 * index, 0.2, 0.3, 1.0)) for index in range(8)], list(range(8)))
    fn.copyUVSet("map1", "map2")
    return mlib.getNode(shape)


def _vertex_face(case):
    """頂点2・フェース1(上の面)の面頂点を返す。"""
    return VertexFace(_mesh(case), (2, 1))


def _vertex_face_pair(case):
    """複数形の確かめ用に、(VertexFaces[(2, 1), (3, 1)], 単数の並び) を返す。"""
    mesh = _mesh(case)
    return VertexFaces(mesh, [(2, 1), (3, 1)]), [VertexFace(mesh, (2, 1)), VertexFace(mesh, (3, 1))]


def _space(kwargs):
    """worldSpace・ws の指定を om2 の空間にする。"""
    return om2.MSpace.kWorld if kwargs.get("worldSpace", kwargs.get("ws", False)) is True else om2.MSpace.kObject


def _numbers(component):
    """面頂点の (頂点, フェース) を返す。"""
    name = component.getName(full=True)
    vertex, face = name.rsplit("[", 2)[1:]
    return int(vertex[:-1]), int(face[:-1])


def _expect_vertex(case, call):
    """頂点2。"""
    case.assertEqual(call.result.index, 2)


def _expect_face(case, call):
    """フェース1。"""
    case.assertEqual(call.result.index, 1)


def _locked_with_space(kwargs):
    """lockedOnly=True は worldSpace・ws と同時に指定できない。"""
    return kwargs.get("lockedOnly") is True and ("worldSpace" in kwargs or "ws" in kwargs)


def _expect_normal(case, call):
    """lockedOnly ならロックされているか、そうでなければ MFnMesh.getFaceVertexNormal と同じ。"""
    vertex, face = _numbers(call.target)
    fn = _fn(call.target.shape.getName(full=True))
    if call.kwargs.get("lockedOnly"):
        frozen = cmds.polyNormalPerVertex(call.target.getName(full=True), query=True, freezeNormal=True)[0]
        case.assertEqual(call.result, frozen)
    else:
        case.assertSequenceAlmostEqual(call.result, fn.getFaceVertexNormal(face, vertex, _space(call.kwargs)), places=5)


def _set_normal_conflict(kwargs):
    """normal と locked のどちらも無い・normal と locked=False・normal 無しの worldSpace・ws・check=True は指定できない。"""
    if kwargs.get("normal") is None:
        if kwargs.get("locked") is None:
            return True
        return "worldSpace" in kwargs or "ws" in kwargs or kwargs.get("check") is True
    return kwargs.get("locked") is False


def _normal_state(case, target):
    """面頂点ごとの法線とロックと、シーンの状態。"""
    shape = target.shape.getName(full=True)
    fn = _fn(shape)
    normals = []
    for face in range(fn.numPolygons):
        normals.extend(tuple(round(value, 4) for value in fn.getFaceVertexNormal(face, vertex)) for vertex in fn.getPolygonVertices(face))
    frozen = cmds.polyNormalPerVertex(shape + ".vtxFace[*][*]", query=True, freezeNormal=True)
    return [normals, frozen, case.sceneState()]


def _unit(values):
    """3成分の値を長さ1にする。"""
    vector = om2.MVector(*list(values)[:3])
    return list(vector.normal())


def _expect_set_normal(case, call):
    """法線を渡したら、その向き(オブジェクト空間)になりロックされる。locked だけなら、ロックの状態になる。"""
    kwargs = call.kwargs
    vertex, face = _numbers(call.target)
    frozen = cmds.polyNormalPerVertex(call.target.getName(full=True), query=True, freezeNormal=True)[0]
    if kwargs.get("normal") is None:
        case.assertEqual(frozen, kwargs["locked"])
        return
    case.assertTrue(frozen)
    if _space(kwargs) == om2.MSpace.kObject:
        actual = _fn(call.target.shape.getName(full=True)).getFaceVertexNormal(face, vertex)
        case.assertSequenceAlmostEqual(actual, _unit(kwargs["normal"]), places=4)


def _expect_tangent(case, call):
    """MFnMesh.getFaceVertexTangent(binormal なら getFaceVertexBinormal)と同じ。"""
    vertex, face = _numbers(call.target)
    fn = _fn(call.target.shape.getName(full=True))
    getter = fn.getFaceVertexBinormal if call.kwargs.get("binormal") else fn.getFaceVertexTangent
    expected = getter(face, vertex, _space(call.kwargs), call.kwargs.get("uvSet") or "map1")
    case.assertSequenceAlmostEqual(call.result, expected, places=5)


def _expect_color(case, call):
    """cs1(None は今のセット cs1)は頂点2の色 (0.2, 0.2, 0.3, 1)、色の無い cs2 は None。"""
    if call.kwargs.get("colorSet") == "cs2":
        case.assertIsNone(call.result)
    else:
        case.assertSequenceAlmostEqual(call.result, (0.2, 0.2, 0.3, 1.0), places=5)


def _color_state(case, target):
    """カラーセットの名前・今のセットと、各セットの面頂点の色と、シーンの状態。"""
    fn = _fn(target.shape.getName(full=True))
    colors = [[tuple(round(value, 5) for value in color) for color in fn.getFaceVertexColors(name)] for name in fn.getColorSetNames()]
    return [fn.getColorSetNames(), fn.currentColorSetName(), colors, case.sceneState()]


def _expect_set_color(case, call):
    """getColor が渡した色(A を省いたら 1)になる。"""
    color = list(call.kwargs["color"])
    if len(color) == 3:
        color.append(1.0)
    case.assertSequenceAlmostEqual(call.target.getColor(colorSet=call.kwargs.get("colorSet")), color, places=5)


def _expect_remove_color(case, call):
    """面頂点の色が無くなる。"""
    case.assertIsNone(call.target.getColor(colorSet=call.kwargs.get("colorSet")))


class VertexFaceArgumentSweepTest(ArgumentSweepCase):
    """VertexFace の公開メソッドの引数を網羅する(複数形は VertexFaces)。"""

    METHODS = (
        Method("getVertex", _vertex_face, expect=_expect_vertex),
        Method("getFace", _vertex_face, expect=_expect_face),
        Method("getNormal", _vertex_face, conflicts=(SPACE, _locked_with_space), expect=_expect_normal, plural=_vertex_face_pair),
        Method(
            "setNormal",
            _vertex_face,
            args=((0.0, 1.0, 0.0),),
            values={"normal": NORMAL_VALUES},
            replace=("normal",),
            invalid={"normal": NORMAL_INVALID},
            conflicts=(SPACE, _set_normal_conflict),
            state=_normal_state,
            expect=_expect_set_normal,
            plural=_vertex_face_pair,
            limit=60,
        ),
        Method(
            "getTangent",
            _vertex_face,
            values={"uvSet": ("map1", "map2", "nope")},
            invalid={"uvSet": (1.5,), "binormal": (1, "yes")},
            conflicts=(SPACE,),
            expect=_expect_tangent,
            plural=_vertex_face_pair,
        ),
        Method(
            "getColor",
            _vertex_face,
            values={"colorSet": ("cs1", "cs2", "nope")},
            invalid={"colorSet": (1.5, "nope")},
            expect=_expect_color,
            plural=_vertex_face_pair,
        ),
        Method(
            "setColor",
            _vertex_face,
            args=((1.0, 0.0, 0.0),),
            values={"color": COLOR_VALUES, "colorSet": ("cs1", "cs2", "nope")},
            replace=("color",),
            invalid={"color": COLOR_INVALID, "colorSet": (1.5, "nope")},
            state=_color_state,
            expect=_expect_set_color,
            plural=_vertex_face_pair,
            limit=60,
        ),
        Method(
            "removeColor",
            _vertex_face,
            values={"colorSet": ("cs1", "cs2", "nope")},
            invalid={"colorSet": (1.5, "nope"), "fast": (1, "yes")},
            state=_color_state,
            expect=_expect_remove_color,
            plural=_vertex_face_pair,
        ),
    )


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
