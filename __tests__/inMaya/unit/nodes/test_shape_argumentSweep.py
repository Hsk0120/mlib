"""Shapeの公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
Locator は Shape の公開メソッドをそのまま使い、自身のメソッドを持たないので、Shape の対象に Locator を使う。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support import argumentTable as table
from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import DELETED_NODE, MISSING_NAME, Lazy, Method

#: 書き込むメソッドの段3の組の上限。
WRITE_LIMIT = 40


class _InNamespace:
    """作るノードがテストの名前空間に入るよう、今の名前空間を切り替える。"""

    def __init__(self, case):
        self.case = case

    def __enter__(self):
        self.previous = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)
        cmds.namespace(setNamespace=":" + self.case.ns)

    def __exit__(self, *exc):
        cmds.namespace(setNamespace=self.previous)


def _known(reason, *patterns):
    return dict.fromkeys(patterns, reason)


def _ls(case, pattern, kind="transform"):
    return cmds.ls(case.ns + ":" + pattern, long=True, type=kind)


def _make_locator(case):
    """Transform(holder)の下の Locator と、移す先(goal・joint)。"""
    holder = case.make("transform", "holder#")
    shape = cmds.createNode("locator", name=case.name("loc#"), parent=holder, skipSelect=True)
    case.make("transform", "goal#")
    case.make("joint", "bone#")
    return mlib.getNode(cmds.ls(shape, long=True)[0])


def _make_mesh_shape(case):
    """ヒストリの無い polyCube の mesh(1cm)。"""
    with _InNamespace(case):
        mesh = cmds.polyCube(name="mesh#", constructionHistory=False)[0]
        cmds.move(1.0, 2.0, 3.0, mesh)
    return mlib.getNode(cmds.listRelatives(mesh, shapes=True, fullPath=True)[0])


def _make_mesh_plural(case):
    singles = [_make_mesh_shape(case), _make_mesh_shape(case)]
    return mlib.Nodes(singles), singles


GOAL = Lazy(lambda case: mlib.getNode(_ls(case, "goal*")[0]), "<goal>")
GOAL_NAME = Lazy(lambda case: _ls(case, "goal*")[0], "'<goalの名前>'")
BONE = Lazy(lambda case: mlib.getNode(_ls(case, "bone*", "joint")[0]), "<joint>")


def _full(call):
    return call.target.getName(full=True)


def _expect_set_parent(case, call):
    parent = call.kwargs["parent"]
    parent = parent.getName(full=True) if isinstance(parent, mlib.Node) else cmds.ls(parent, long=True)[0]
    parents = cmds.listRelatives(call.target.getName(short=True), allParents=True, fullPath=True)
    case.assertIn(parent, parents)
    if not call.kwargs.get("add"):
        case.assertEqual(len(parents), 1)


def _expect_scale(case, call):
    kwargs = call.kwargs
    if kwargs.get("worldSpace", kwargs.get("ws", False)) or kwargs.get("indices") is not None or tuple(kwargs.get("pivot", (0, 0, 0))) != (0, 0, 0):
        return
    scale = kwargs["scale"]
    scale = (scale,) * 3 if isinstance(scale, (int, float)) else tuple(scale)
    point = cmds.pointPosition(_full(call) + ".vtx[0]", local=True)
    case.assertSequenceAlmostEqual(point, [-0.5 * scale[0], -0.5 * scale[1], 0.5 * scale[2]], places=5)


METHODS = (
    Method(
        "setParent",
        _make_locator,
        args=(GOAL,),
        values={"parent": (GOAL, GOAL_NAME, BONE)},
        replace=("parent",),
        invalid={"parent": (None, DELETED_NODE, MISSING_NAME, 1.5, Lazy(lambda case: mlib.createNode("multiplyDivide", name=case.name("dg#")), "<DGノード>"))},
        expect=_expect_set_parent,
        limit=WRITE_LIMIT,
    ),
    Method(
        "scaleGeometry",
        _make_mesh_shape,
        args=(2.0,),
        values={"scale": (2.0, 1, (1.0, 2.0, 3.0), [0.5, 0.5, 0.5], 0.0, -1.0), "pivot": ((1.0, 0.0, 0.0), [0, 0, 0]), "indices": ([0, 1], (7,), [])},
        replace=("scale",),
        invalid={"scale": ("a", (1.0, 2.0), float("nan"), None), "pivot": (1.5, "abc", (1.0, 2.0), None), "indices": ([100], [-1], ["a"], 1.5)},
        conflicts=(("worldSpace", "ws"),),
        expect=_expect_scale,
        plural=_make_mesh_plural,
        limit=WRITE_LIMIT,
    ),
)


class _ShapeSweepCase(ArgumentSweepCase):
    """書き込むメソッドの複数形の確かめで、作り直した後のノードから値(Lazy)を作り直す(findings4/sweep-dag.md の部品への要望)。"""

    def _check_plural(self, method, kwargs, raises, result, after):
        self.fresh(method)
        plural, _singles = method.plural(self)
        getattr(plural, method.name)(**self._resolve(kwargs))
        plural_after = self.sceneState()
        self.fresh(method)
        _plural, singles = method.plural(self)
        resolved = self._resolve(kwargs)
        for single in singles:
            getattr(single, method.name)(**resolved)
        self.assertTrue(table.same(plural_after, self.sceneState()), "複数形と単数の並びでシーンの結果が違う")


class ShapeArgumentSweepTest(_ShapeSweepCase):
    """Shape(Locator)の公開メソッドの引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
