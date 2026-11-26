"""Vertex・Vertices の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

座標の取得・設定(PointComponent から受け継ぐもの)は ``test_pointComponent_argumentSweep.py`` で確かめる。
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

from mlib.components import Vertex, Vertices

#: 長い名前と短縮名の組(同時に指定できない)。
SPACE = ("worldSpace", "ws")
#: 色の候補(RGB・RGBA・om2 の色・リスト・範囲の外)。
COLOR_VALUES = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.5), om2.MColor((0.2, 0.3, 0.4, 1.0)), [0.2, 0.3, 0.4], (2.0, -1.0, 0.5))
#: 色の段2の誤った値(成分の数・型・有限でない値)。
COLOR_INVALID = ((1.0, 2.0), (1.0, 2.0, 3.0, 4.0, 5.0), "abc", None, (float("nan"), 0.0, 0.0), object())


def _mesh(case):
    """移動・回転・拡大した、1辺2cm の履歴なし polyCube の Mesh を返す。

    カラーセット ``cs1``(頂点 i の色は (0.1i, 0.2, 0.3, 1))を今のセットにし、色の無いカラーセット ``cs2`` も持つ。
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
    return mlib.getNode(shape)


def _fn(shape):
    """メッシュの名前から MFnMesh を返す。"""
    selection = om2.MSelectionList()
    selection.add(shape)
    return om2.MFnMesh(selection.getDagPath(0))


def _vertex(case):
    """頂点3を返す。"""
    return Vertex(_mesh(case), 3)


def _vertex_pair(case):
    """複数形の確かめ用に、(Vertices[3, 5], 単数の並び) を返す。"""
    mesh = _mesh(case)
    return Vertices(mesh, [3, 5]), [Vertex(mesh, 3), Vertex(mesh, 5)]


def _vertices(case):
    """頂点 [2, 3] の Vertices を返す。"""
    return Vertices(_mesh(case), [2, 3])


def _color_state(case, target):
    """カラーセットの名前・今のセットと、各セットの面頂点の色と、シーンの状態。"""
    fn = _fn(target.shape.getName(full=True))
    colors = [[tuple(round(value, 5) for value in color) for color in fn.getFaceVertexColors(name)] for name in fn.getColorSetNames()]
    return [fn.getColorSetNames(), fn.currentColorSetName(), colors, case.sceneState()]


def _expect_color(case, call):
    """cs1(None は今のセット cs1)は (0.1i, 0.2, 0.3, 1)、色の無い cs2 は None。"""
    if call.kwargs.get("colorSet") == "cs2":
        case.assertIsNone(call.result)
    else:
        case.assertSequenceAlmostEqual(call.result, (0.1 * call.target.index, 0.2, 0.3, 1.0), places=5)


def _expect_set_color(case, call):
    """getColor が渡した色(A を省いたら 1)になる。"""
    color = list(call.kwargs["color"])
    if len(color) == 3:
        color.append(1.0)
    case.assertSequenceAlmostEqual(call.target.getColor(colorSet=call.kwargs.get("colorSet")), color, places=5)


def _expect_normal(case, call):
    """MFnMesh.getVertexNormal(angleWeighted, 空間)と同じ。"""
    world = call.kwargs.get("worldSpace", call.kwargs.get("ws", False)) is True
    fn = _fn(call.target.shape.getName(full=True))
    expected = fn.getVertexNormal(call.target.index, call.kwargs.get("angleWeighted", False), om2.MSpace.kWorld if world else om2.MSpace.kObject)
    case.assertSequenceAlmostEqual(call.result, expected, places=5)


def _neighbors(shape, indices):
    """cmds.polyInfo で、頂点にエッジでつながる頂点の番号を集める。"""
    result = set()
    for index in indices:
        for edge in cmds.polyInfo(f"{shape}.vtx[{index}]", vertexToEdge=True)[0].split(":")[1].split():
            result.update(int(item) for item in cmds.polyInfo(f"{shape}.e[{edge}]", edgeToVertex=True)[0].split(":")[1].split()[:2])
    return result


def _expect_grow(case, call):
    """持っている頂点のあとに、エッジでつながる頂点を番号の順に足す。"""
    indices = list(call.target.indices)
    added = sorted(_neighbors(call.target.shape.getName(full=True), indices).difference(indices))
    case.assertEqual(list(call.result.indices), indices + added)


class VertexArgumentSweepTest(ArgumentSweepCase):
    """Vertex の公開メソッドの引数を網羅する。"""

    METHODS = (
        Method("getFaces", _vertex),
        Method("getEdges", _vertex),
        Method("getConnected", _vertex),
        Method("getVertexFaces", _vertex),
        Method("getUVs", _vertex),
        Method("isOnBoundary", _vertex),
        Method(
            "getColor", _vertex, values={"colorSet": ("cs1", "cs2", "nope")}, invalid={"colorSet": (1.5, "nope")}, expect=_expect_color, plural=_vertex_pair
        ),
        Method(
            "setColor",
            _vertex,
            args=((1.0, 0.0, 0.0),),
            values={"color": COLOR_VALUES, "colorSet": ("cs1", "cs2", "nope")},
            replace=("color",),
            invalid={"color": COLOR_INVALID, "colorSet": (1.5, "nope")},
            state=_color_state,
            expect=_expect_set_color,
            plural=_vertex_pair,
            limit=60,
        ),
        Method("getNormal", _vertex, conflicts=(SPACE,), expect=_expect_normal, plural=_vertex_pair),
    )


class VerticesArgumentSweepTest(ArgumentSweepCase):
    """Vertices の公開メソッドの引数を網羅する。"""

    METHODS = (Method("grow", _vertices, writes=False, expect=_expect_grow), Method("shrink", _vertices, writes=False), Method("getFaces", _vertices))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
