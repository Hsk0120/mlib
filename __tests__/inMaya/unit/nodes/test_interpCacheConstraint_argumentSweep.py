"""補間キャッシュを持つコンストレイント(OrientConstraint・ParentConstraint の共通の基底)の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Method

#: 書き込むメソッドの段3の組の上限。
WRITE_LIMIT = 40


class _InNamespace:
    """作るコンストレイント・animCurve がテストの名前空間に入るよう、今の名前空間を切り替える。"""

    def __init__(self, case):
        self.case = case

    def __enter__(self):
        self.previous = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)
        cmds.namespace(setNamespace=":" + self.case.ns)

    def __exit__(self, *exc):
        cmds.namespace(setNamespace=self.previous)


def _make_orient(case):
    """ターゲット2つの orientConstraint(interpType をキャッシュにする)。ウェイトにキーを打つ。"""
    first = case.make("transform", "targetA#")
    second = case.make("transform", "targetB#")
    cmds.setAttr(second + ".rotate", 0.0, 90.0, 0.0)
    driven = case.make("transform", "driven#")
    with _InNamespace(case):
        constraint = cmds.orientConstraint(first, second, driven, name="oc#")[0]
        cmds.setAttr(constraint + ".interpType", 3)
        weights = cmds.orientConstraint(constraint, query=True, weightAliasList=True)
        for time, value in ((1, 0.0), (10, 1.0)):
            cmds.setKeyframe(constraint, attribute=weights[0], time=time, value=value)
    return mlib.getNode(cmds.ls(constraint, long=True)[0])


def _make_plural(case):
    singles = [_make_orient(case), _make_orient(case)]
    return mlib.Nodes(singles), singles


METHODS = (
    Method(
        "createCache",
        _make_orient,
        args=(1, 10),
        values={"start": (1, 0.5, -5), "end": (10, 10.5, 1), "timeUnit": ("frame", "sec")},
        replace=("start", "end"),
        invalid={"start": ("a", None, float("nan"), float("inf")), "end": ("a", None, float("nan"), 0), "timeUnit": (1.5, "__argumentSweepInvalid__")},
        plural=_make_plural,
        limit=WRITE_LIMIT,
    ),
)


class InterpCacheConstraintArgumentSweepTest(ArgumentSweepCase):
    """OrientConstraint の createCache(補間キャッシュの共通の基底のメソッド)の引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
