"""Edge・Edges の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import math
import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Method

from mlib.components import Edge, Edges

#: 長い名前と短縮名の組(同時に指定できない)。
SPACE = ("worldSpace", "ws")


def _mesh(case):
    """移動・回転・拡大した、1辺2cm の履歴なし polyCube の Mesh を返す。"""
    transform = cmds.polyCube(name=case.name("cube#"), width=2, height=2, depth=2, constructionHistory=False)[0]
    cmds.setAttr(transform + ".translate", 1.0, 2.0, 3.0)
    cmds.setAttr(transform + ".rotate", 0.0, 30.0, 0.0)
    cmds.setAttr(transform + ".scale", 2.0, 1.0, 0.5)
    return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])


def _edge(case):
    """エッジ1を返す。"""
    return Edge(_mesh(case), 1)


def _edge_pair(case):
    """複数形の確かめ用に、(Edges[1, 4], 単数の並び) を返す。"""
    mesh = _mesh(case)
    return Edges(mesh, [1, 4]), [Edge(mesh, 1), Edge(mesh, 4)]


def _edges(case):
    """エッジ [1, 4] の Edges を返す。"""
    return Edges(_mesh(case), [1, 4])


def _world(kwargs):
    """worldSpace・ws のどちらかで True を指定したか。"""
    return kwargs.get("worldSpace", kwargs.get("ws", False)) is True


def _ends(edge, world):
    """エッジの両端の頂点の座標を cmds で読む。"""
    shape = edge.shape.getName(full=True)
    numbers = [int(item) for item in cmds.polyInfo(f"{shape}.e[{edge.index}]", edgeToVertex=True)[0].split(":")[1].split()[:2]]
    return [cmds.xform(f"{shape}.vtx[{number}]", query=True, translation=True, worldSpace=world, objectSpace=not world) for number in numbers]


def _expect_length(case, call):
    """両端の頂点の距離。"""
    first, second = _ends(call.target, _world(call.kwargs))
    case.assertAlmostEqual(call.result, math.sqrt(sum((a - b) ** 2 for a, b in zip(first, second))), places=5)


def _expect_center(case, call):
    """両端の頂点の中点。"""
    first, second = _ends(call.target, _world(call.kwargs))
    case.assertSequenceAlmostEqual(call.result, [(a + b) / 2.0 for a, b in zip(first, second)], places=5)


def _expect_loop(case, call):
    """cmds.polySelect の edgeLoop(ring なら edgeRing)と同じエッジ。"""
    shape = call.target.shape.getName(full=True)
    flag = "edgeRing" if call.kwargs.get("ring") else "edgeLoop"
    starts = getattr(call.target, "indices", None) or [call.target.index]
    expected = set()
    for start in starts:
        expected.update(cmds.polySelect(shape, noSelection=True, **{flag: start}) or [])
    case.assertEqual(set(call.result.indices), expected)


def _smooth_state(case, target):
    """エッジごとのソフト・ハードと、シーンの状態。"""
    selection = om2.MSelectionList()
    selection.add(target.shape.getName(full=True))
    fn = om2.MFnMesh(selection.getDagPath(0))
    return [[fn.isEdgeSmooth(index) for index in range(fn.numEdges)], case.sceneState()]


def _expect_smooth(case, call):
    """エッジのソフト・ハードが state になる。"""
    case.assertEqual(call.target.isSmooth(), call.kwargs.get("state", True))


class EdgeArgumentSweepTest(ArgumentSweepCase):
    """Edge の公開メソッドの引数を網羅する。"""

    METHODS = (
        Method("getVertices", _edge),
        Method("getFaces", _edge),
        Method("getLength", _edge, conflicts=(SPACE,), expect=_expect_length, plural=_edge_pair),
        Method("getCenter", _edge, conflicts=(SPACE,), expect=_expect_center, plural=_edge_pair),
        Method("getLoop", _edge, expect=_expect_loop, plural=_edge_pair),
        Method("getConnected", _edge),
        Method("isOnBoundary", _edge),
        Method("isSmooth", _edge),
        Method("setSmooth", _edge, state=_smooth_state, expect=_expect_smooth, plural=_edge_pair),
    )


class EdgesArgumentSweepTest(ArgumentSweepCase):
    """Edges の公開メソッドの引数を網羅する。"""

    METHODS = (Method("getVertices", _edges), Method("getFaces", _edges), Method("getLoop", _edges, expect=_expect_loop))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
